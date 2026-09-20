from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.text_normalization import (
    TextSafetyValidationError,
    validate_text_safety,
)
from aria_observability import (
    StructuredEventLogger,
    TraceContext,
    bind_trace_context,
)

from app.application.context_parser import (
    EmptyCanonicalTextError,
    SourceVersionInput,
    TextParser,
)
from app.application.parser_metrics import ParserMetrics
from app.application.ports import JobExecutionGuard

PARSER_MESSAGE_VERSION = "1"
PARSER_JOB_TYPE = "context_source_parse"
TXT_MIME_TYPE = "text/plain"
TXT_MAX_BYTES = 200_000


class ParserConsumerError(RuntimeError):
    """A safe, bounded TXT Parser consumer failure."""


class ParserMessageValidationError(ParserConsumerError):
    """The Queue message does not match the frozen minimal envelope."""


class ParserRuntimePersistenceError(ParserConsumerError):
    """A processing or finalization transaction did not commit."""


class StoredObjectReadError(ParserConsumerError):
    def __init__(self, *, retryable: bool, reason_code: str) -> None:
        super().__init__("Private object read failed")
        self.retryable = retryable
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ParserJobMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    def __post_init__(self) -> None:
        if self.message_version != PARSER_MESSAGE_VERSION:
            raise ParserMessageValidationError("Unsupported Parser message version")
        if not isinstance(self.outbox_event_id, UUID) or not isinstance(self.job_id, UUID):
            raise ParserMessageValidationError("Parser message identifiers must be UUIDs")

    @classmethod
    def from_payload(cls, payload: object) -> ParserJobMessage:
        if not isinstance(payload, dict) or set(payload) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise ParserMessageValidationError("Parser message shape is invalid")
        try:
            return cls(
                message_version=payload["message_version"],
                outbox_event_id=UUID(str(payload["outbox_event_id"])),
                job_id=UUID(str(payload["job_id"])),
            )
        except (TypeError, ValueError):
            raise ParserMessageValidationError("Parser message values are invalid") from None


@dataclass(frozen=True, slots=True)
class ParserJobInput:
    job_id: UUID
    account_id: UUID
    project_id: UUID
    correlation_id: UUID
    source_id: UUID
    source_version_id: UUID
    source_type: Literal["text", "file"]
    raw_text: str | None
    storage_ref: str | None
    mime_type: str | None
    available_at: datetime
    first_attempt: bool


@dataclass(frozen=True, slots=True)
class ParserConsumerResult:
    status: Literal["succeeded", "failed", "suppressed", "already_completed"]
    error_code: str | None = None


class ParserJobStore(Protocol):
    async def prepare(self, message: ParserJobMessage) -> ParserJobInput: ...

    async def finalize_success(
        self,
        job: ParserJobInput,
        *,
        canonical_value: str,
        canonical_hash: str,
        metadata: dict[str, object],
    ) -> None: ...

    async def finalize_failure(self, job: ParserJobInput, *, error_code: str) -> None: ...


class PrivateObjectReader(Protocol):
    async def read_private(self, *, storage_reference: str) -> bytes: ...


class TxtParserConsumer:
    def __init__(
        self,
        *,
        guard: JobExecutionGuard,
        store: ParserJobStore,
        parser: TextParser,
        object_reader: PrivateObjectReader,
        metrics: ParserMetrics | None,
        event_logger: StructuredEventLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._guard = guard
        self._store = store
        self._parser = parser
        self._object_reader = object_reader
        self._metrics = metrics
        self._event_logger = event_logger
        self._clock = clock

    async def execute(self, message: ParserJobMessage) -> ParserConsumerResult:
        acquisition = await self._guard.acquire(message.job_id)
        if acquisition == "already_in_progress":
            self._event_logger.emit(
                "worker.job_duplicate_suppressed",
                job_id=str(message.job_id),
                reason_code="already_in_progress",
                status="suppressed",
            )
            return ParserConsumerResult(status="suppressed")
        if acquisition == "already_completed":
            self._event_logger.emit(
                "worker.job_already_completed",
                job_id=str(message.job_id),
                reason_code="already_completed",
                status="succeeded",
            )
            return ParserConsumerResult(status="already_completed")

        job: ParserJobInput | None = None
        try:
            job = await self._store.prepare(message)
            with _job_trace(job):
                return await self._execute_acquired(job)
        except ParserRuntimePersistenceError:
            await self._guard.release(message.job_id)
            trace = _job_trace(job) if job is not None else nullcontext()
            with trace:
                self._event_logger.emit(
                    "worker.job_execution_interrupted",
                    level="ERROR",
                    job_id=str(message.job_id),
                    reason_code="persistence_unavailable",
                    error_code="PARSER_PERSISTENCE_UNAVAILABLE",
                    status="recoverable",
                )
            raise
        except BaseException:
            await self._guard.release(message.job_id)
            raise

    async def _execute_acquired(self, job: ParserJobInput) -> ParserConsumerResult:
        if job.first_attempt:
            queue_wait_ms = max(
                0.0,
                (self._clock() - job.available_at).total_seconds() * 1000,
            )
            if self._metrics is not None:
                with suppress(Exception):
                    self._metrics.observe_queue_wait(queue_wait_ms, parser_type="text")
        self._event_logger.emit(
            "worker.job_execution_started",
            job_id=str(job.job_id),
            source_version_id=str(job.source_version_id),
            job_type=PARSER_JOB_TYPE,
            status="running",
        )

        try:
            raw_value = await self._resolve_text(job)
            parsed = self._parser.parse(
                SourceVersionInput(id=job.source_version_id, raw_text=raw_value)
            )
        except StoredObjectReadError as error:
            error_code = (
                "PARSER_STORAGE_UNAVAILABLE"
                if error.retryable
                else "PARSER_STORAGE_REJECTED"
            )
            return await self._fail(job, error_code)
        except EmptyCanonicalTextError:
            return await self._fail(job, "PARSER_EMPTY_CONTENT")
        except (TextSafetyValidationError, UnicodeDecodeError):
            return await self._fail(job, "PARSER_INVALID_INPUT")

        canonical_hash = sha256(parsed.canonical_text.encode("utf-8")).hexdigest()
        await self._store.finalize_success(
            job,
            canonical_value=parsed.canonical_text,
            canonical_hash=canonical_hash,
            metadata=parsed.metadata,
        )
        await self._guard.complete(job.job_id)
        self._event_logger.emit(
            "context_source_version.ready",
            job_id=str(job.job_id),
            source_version_id=str(job.source_version_id),
            status="ready",
        )
        self._event_logger.emit(
            "worker.job_execution_completed",
            job_id=str(job.job_id),
            job_type=PARSER_JOB_TYPE,
            status="succeeded",
        )
        return ParserConsumerResult(status="succeeded")

    async def _resolve_text(self, job: ParserJobInput) -> str:
        if job.source_type == "text":
            if job.raw_text is None:
                raise TextSafetyValidationError("Stored text is unavailable")
            return validate_text_safety(job.raw_text)
        if job.mime_type != TXT_MIME_TYPE or job.storage_ref is None:
            raise TextSafetyValidationError("Stored TXT metadata is invalid")
        content = await self._object_reader.read_private(storage_reference=job.storage_ref)
        if len(content) > TXT_MAX_BYTES:
            raise TextSafetyValidationError("Stored TXT exceeds the approved byte limit")
        decoded = content.decode("utf-8", errors="strict")
        return validate_text_safety(decoded)

    async def _fail(self, job: ParserJobInput, error_code: str) -> ParserConsumerResult:
        await self._store.finalize_failure(job, error_code=error_code)
        await self._guard.complete(job.job_id)
        self._event_logger.emit(
            "context_source_version.failed",
            level="ERROR",
            job_id=str(job.job_id),
            source_version_id=str(job.source_version_id),
            error_code=error_code,
            status="failed",
        )
        return ParserConsumerResult(status="failed", error_code=error_code)


def _job_trace(job: ParserJobInput) -> AbstractContextManager[None]:
    return bind_trace_context(
        TraceContext(
            correlation_id=str(job.correlation_id),
            account_id=str(job.account_id),
            project_id=str(job.project_id),
            job_id=str(job.job_id),
        )
    )
