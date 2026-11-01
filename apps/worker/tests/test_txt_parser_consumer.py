from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import create_event_logger

from app.application.context_parser import CanonicalTextParser
from app.application.txt_parser_consumer import (
    ParserConsumerResult,
    ParserJobInput,
    ParserJobMessage,
    ParserMessageValidationError,
    ParserRuntimePersistenceError,
    StoredObjectReadError,
    TxtParserConsumer,
)


@dataclass
class _Guard:
    result: str = "acquired"
    completed: list[UUID] = field(default_factory=list)
    released: list[UUID] = field(default_factory=list)

    async def acquire(self, job_id: UUID) -> str:
        del job_id
        return self.result

    async def complete(self, job_id: UUID) -> None:
        self.completed.append(job_id)

    async def release(self, job_id: UUID) -> None:
        self.released.append(job_id)


@dataclass
class _Store:
    job: ParserJobInput
    success: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    fail_on: str | None = None

    async def prepare(self, message: ParserJobMessage) -> ParserJobInput:
        assert message.job_id == self.job.job_id
        if self.fail_on == "prepare":
            raise ParserRuntimePersistenceError
        return self.job

    async def finalize_success(
        self,
        job: ParserJobInput,
        *,
        canonical_value: str,
        canonical_hash: str,
        metadata: dict[str, object],
    ) -> None:
        assert job == self.job
        if self.fail_on == "success":
            raise ParserRuntimePersistenceError
        self.success.append((canonical_value, canonical_hash, metadata))

    async def finalize_failure(self, job: ParserJobInput, *, error_code: str) -> None:
        assert job == self.job
        if self.fail_on == "failure":
            raise ParserRuntimePersistenceError
        self.failures.append(error_code)


@dataclass
class _Reader:
    value: bytes = b""
    error: StoredObjectReadError | None = None
    references: list[str] = field(default_factory=list)

    async def read_private(self, *, storage_reference: str) -> bytes:
        self.references.append(storage_reference)
        if self.error is not None:
            raise self.error
        return self.value


@dataclass
class _Metrics:
    queue_waits: list[float] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)

    def observe_queue_wait(self, duration_ms: float, *, parser_type: str) -> None:
        assert parser_type == "text"
        self.queue_waits.append(duration_ms)

    def observe_parse_latency(
        self, duration_ms: float, *, parser_type: str, outcome: str
    ) -> None:
        assert parser_type == "text"
        self.latencies.append(duration_ms)

    def record_parse_outcome(
        self, *, parser_type: str, outcome: str, failure_class: str | None = None
    ) -> None:
        del failure_class
        assert parser_type == "text"
        self.outcomes.append(outcome)


def _message(job_id: UUID) -> ParserJobMessage:
    return ParserJobMessage(
        message_version="1",
        outbox_event_id=uuid4(),
        job_id=job_id,
    )


def _job(*, source_type: str = "file", first_attempt: bool = True) -> ParserJobInput:
    now = datetime(2026, 9, 15, 10, 0, tzinfo=UTC)
    return ParserJobInput(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        source_id=uuid4(),
        source_version_id=uuid4(),
        source_type=source_type,  # type: ignore[arg-type]
        raw_text="متن   مستقیم\r\nدوم" if source_type == "text" else None,
        storage_ref="tenant/project/source/version.txt" if source_type == "file" else None,
        mime_type="text/plain" if source_type == "file" else None,
        available_at=now - timedelta(seconds=2),
        first_attempt=first_attempt,
    )


def _consumer(
    job: ParserJobInput,
    *,
    guard: _Guard | None = None,
    store: _Store | None = None,
    reader: _Reader | None = None,
    metrics: _Metrics | None = None,
    stream: StringIO | None = None,
) -> tuple[TxtParserConsumer, _Guard, _Store, _Reader, _Metrics, StringIO]:
    resolved_guard = guard or _Guard()
    resolved_store = store or _Store(job)
    resolved_reader = reader or _Reader("متن   فایل\r\nدوم".encode())
    resolved_metrics = metrics or _Metrics()
    resolved_stream = stream or StringIO()
    logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=resolved_stream,
    )
    return (
        TxtParserConsumer(
            guard=resolved_guard,  # type: ignore[arg-type]
            store=resolved_store,
            parser=CanonicalTextParser(metrics=resolved_metrics, event_logger=logger),  # type: ignore[arg-type]
            object_reader=resolved_reader,
            metrics=resolved_metrics,  # type: ignore[arg-type]
            event_logger=logger,
            clock=lambda: datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
        ),
        resolved_guard,
        resolved_store,
        resolved_reader,
        resolved_metrics,
        resolved_stream,
    )


def test_message_contract_is_exact_and_versioned() -> None:
    job_id = uuid4()
    event_id = uuid4()
    parsed = ParserJobMessage.from_payload(
        {"message_version": "1", "outbox_event_id": str(event_id), "job_id": str(job_id)}
    )
    assert parsed == ParserJobMessage("1", event_id, job_id)

    with pytest.raises(ParserMessageValidationError):
        ParserJobMessage.from_payload(
            {
                "message_version": "1",
                "outbox_event_id": str(event_id),
                "job_id": str(job_id),
                "account_id": str(uuid4()),
            }
        )
    with pytest.raises(ParserMessageValidationError):
        ParserJobMessage.from_payload(
            {"message_version": "2", "outbox_event_id": str(event_id), "job_id": str(job_id)}
        )


def test_file_consumer_revalidates_normalizes_hashes_and_finalizes() -> None:
    job = _job()
    consumer, guard, store, reader, metrics, stream = _consumer(job)

    result = asyncio.run(consumer.execute(_message(job.job_id)))

    assert result == ParserConsumerResult(status="succeeded")
    assert reader.references == ["tenant/project/source/version.txt"]
    assert store.success == [
        (
            "متن فایل\nدوم",
            hashlib.sha256("متن فایل\nدوم".encode()).hexdigest(),
            {},
        )
    ]
    assert guard.completed == [job.job_id]
    assert guard.released == []
    assert metrics.queue_waits == [2000.0]
    assert metrics.outcomes == ["success"]
    assert "متن فایل" not in stream.getvalue()
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert any(event.get("source_version_id") == str(job.source_version_id) for event in events)
    assert all(event["correlation_id"] == str(job.correlation_id) for event in events)
    assert all("source_id" not in event for event in events)


@pytest.mark.parametrize(
    ("content", "error_code"),
    [
        (b"\xff", "PARSER_INVALID_INPUT"),
        (b"safe\x00unsafe", "PARSER_INVALID_INPUT"),
        (b" \t\r\n", "PARSER_EMPTY_CONTENT"),
    ],
)
def test_untrusted_stored_txt_is_rejected_atomically(content: bytes, error_code: str) -> None:
    job = _job()
    store = _Store(job)
    consumer, guard, _, _, _, stream = _consumer(job, store=store, reader=_Reader(content))

    result = asyncio.run(consumer.execute(_message(job.job_id)))

    assert result == ParserConsumerResult(status="failed", error_code=error_code)
    assert store.success == []
    assert store.failures == [error_code]
    assert guard.completed == [job.job_id]
    assert "raw_text" not in stream.getvalue()
    assert "canonical_text" not in stream.getvalue()


def test_storage_failure_maps_to_bounded_error_without_provider_detail() -> None:
    job = _job()
    provider_error = StoredObjectReadError(
        retryable=True, reason_code="provider_network_transient"
    )
    consumer, _, store, _, _, stream = _consumer(job, reader=_Reader(error=provider_error))

    result = asyncio.run(consumer.execute(_message(job.job_id)))

    assert result.error_code == "PARSER_STORAGE_UNAVAILABLE"
    assert store.failures == ["PARSER_STORAGE_UNAVAILABLE"]
    assert "provider_network_transient" not in stream.getvalue()


def test_commit_failure_releases_guard_and_keeps_execution_recoverable() -> None:
    job = _job()
    store = _Store(job, fail_on="success")
    consumer, guard, _, _, _, stream = _consumer(job, store=store)

    with pytest.raises(ParserRuntimePersistenceError):
        asyncio.run(consumer.execute(_message(job.job_id)))

    assert guard.completed == []
    assert guard.released == [job.job_id]
    event = json.loads(stream.getvalue().splitlines()[-1])
    assert event["event_name"] == "worker.job_execution_interrupted"
    assert event["status"] == "recoverable"


def test_recovery_does_not_record_queue_wait_or_create_new_identity() -> None:
    job = replace(_job(source_type="text"), first_attempt=False)
    consumer, _, store, reader, metrics, _ = _consumer(job)

    assert asyncio.run(consumer.execute(_message(job.job_id))).status == "succeeded"

    assert metrics.queue_waits == []
    assert reader.references == []
    assert store.job.source_id == job.source_id
    assert store.job.source_version_id == job.source_version_id


@pytest.mark.parametrize("guard_result", ["already_in_progress", "already_completed"])
def test_duplicate_delivery_is_a_successful_noop(guard_result: str) -> None:
    job = _job()
    guard = _Guard(result=guard_result)
    consumer, _, store, reader, _, _ = _consumer(job, guard=guard)

    result = asyncio.run(consumer.execute(_message(job.job_id)))

    assert result.status in {"suppressed", "already_completed"}
    assert store.success == []
    assert store.failures == []
    assert reader.references == []
