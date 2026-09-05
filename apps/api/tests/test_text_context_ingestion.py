from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.ports import ContextSourceRepository
from app.modules.context.application.text_context_ingestion import (
    CreateTextContextCommand,
    CreateTextContextUseCase,
    TextContextIdempotencyConflict,
    TextContextNotFound,
)
from app.modules.context.application.text_ingestion_ports import (
    TextContextIngestionUnitOfWork,
)
from app.modules.context.domain.context_source import (
    ContextSource,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
    text_context_checksum,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent
from app.modules.projects.application.ports import ProjectRepository
from app.shared.idempotency import IdempotencyRepository, IdempotencyReservation


class FakeProjects:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists

    async def get(self, *, account_id: UUID, project_id: UUID) -> object | None:
        del account_id, project_id
        return object() if self.exists else None


class FakeContextSources:
    def __init__(self) -> None:
        self.sources: list[ContextSource] = []
        self.versions: list[ContextSourceVersion] = []

    async def add_source(self, source: NewContextSource) -> ContextSource:
        now = datetime.now(UTC)
        persisted = ContextSource(**asdict(source), created_at=now, updated_at=now)
        self.sources.append(persisted)
        return persisted

    async def add_version(self, version: NewContextSourceVersion) -> ContextSourceVersion:
        persisted = ContextSourceVersion(**asdict(version), created_at=datetime.now(UTC))
        self.versions.append(persisted)
        return persisted


class FakeJobs:
    def __init__(self) -> None:
        self.rows: list[Job] = []

    async def add(self, job: NewJob) -> Job:
        persisted = Job(
            **asdict(job),
            started_at=None,
            finished_at=None,
            error_code=None,
            error_detail=None,
            created_at=datetime.now(UTC),
        )
        self.rows.append(persisted)
        return persisted


class FakeOutbox:
    def __init__(self) -> None:
        self.rows: list[OutboxEvent] = []

    async def add(self, event: NewOutboxEvent) -> OutboxEvent:
        persisted = OutboxEvent(
            **asdict(event), created_at=datetime.now(UTC), published_at=None
        )
        self.rows.append(persisted)
        return persisted


class FakeIdempotency:
    def __init__(self) -> None:
        self.request_hash: str | None = None
        self.response_status: int | None = None
        self.response_ref: dict[str, object] | None = None
        self.expires_at: datetime | None = None

    async def reserve(
        self,
        *,
        record_id: UUID,
        account_id: UUID,
        actor_id: UUID,
        route_key: str,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> IdempotencyReservation:
        del record_id, account_id, actor_id, route_key, idempotency_key
        if self.expires_at is not None and self.expires_at <= now:
            self.request_hash = None
            self.response_status = None
            self.response_ref = None
        if self.request_hash is None:
            self.request_hash = request_hash
            self.expires_at = expires_at
            return IdempotencyReservation(True, request_hash, None, None)
        return IdempotencyReservation(
            False,
            self.request_hash,
            self.response_status,
            self.response_ref,
        )

    async def complete(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        route_key: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_ref: dict[str, object],
    ) -> None:
        del account_id, actor_id, route_key, idempotency_key
        assert self.request_hash == request_hash
        self.response_status = response_status
        self.response_ref = response_ref


class FakeIngestionUnitOfWork(TextContextIngestionUnitOfWork):
    def __init__(self, *, project_exists: bool = True) -> None:
        self.project_adapter = FakeProjects(project_exists)
        self.context_adapter = FakeContextSources()
        self.job_adapter = FakeJobs()
        self.outbox_adapter = FakeOutbox()
        self.idempotency_adapter = FakeIdempotency()
        self.commits = 0

    @property
    def projects(self) -> ProjectRepository:
        return cast(ProjectRepository, self.project_adapter)

    @property
    def context_sources(self) -> ContextSourceRepository:
        return cast(ContextSourceRepository, self.context_adapter)

    @property
    def jobs(self) -> JobRepository:
        return cast(JobRepository, self.job_adapter)

    @property
    def outbox(self) -> OutboxRepository:
        return cast(OutboxRepository, self.outbox_adapter)

    @property
    def idempotency(self) -> IdempotencyRepository:
        return self.idempotency_adapter

    async def __aenter__(self) -> FakeIngestionUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.commits += 1


def _context() -> TenantContext:
    return TenantContext(
        subject_id=uuid4(),
        account_id=uuid4(),
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def _execute(
    service: CreateTextContextUseCase,
    context: TenantContext,
    command: CreateTextContextCommand,
):
    async def scenario():
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(command.correlation_id))
        ):
            return await service.execute(context, command)

    return asyncio.run(scenario())


def test_ingestion_preserves_text_and_atomically_schedules_content_free_job() -> None:
    unit_of_work = FakeIngestionUnitOfWork()
    stream = StringIO()
    service = CreateTextContextUseCase(lambda: unit_of_work, _logger(stream))
    context = _context()
    raw_text = "  متن محرمانه\r\nبا فاصله  "
    command = CreateTextContextCommand(
        project_id=uuid4(),
        raw_text=raw_text,
        idempotency_key="request-key",
        correlation_id=uuid4(),
    )

    accepted = _execute(service, context, command)

    assert unit_of_work.commits == 1
    source = unit_of_work.context_adapter.sources[0]
    version = unit_of_work.context_adapter.versions[0]
    job = unit_of_work.job_adapter.rows[0]
    outbox = unit_of_work.outbox_adapter.rows[0]
    assert source.raw_text == raw_text
    assert source.checksum == text_context_checksum(raw_text)
    assert version.source_id == source.id and version.parse_status == "pending"
    assert job.payload_ref == {
        "source_id": str(source.id),
        "source_version_id": str(version.id),
    }
    assert outbox.payload["jobId"] == str(job.id)
    assert accepted.source_id == source.id and accepted.job_id == job.id
    assert raw_text not in json.dumps(job.payload_ref, ensure_ascii=False)
    assert raw_text not in json.dumps(outbox.payload, ensure_ascii=False)
    assert raw_text not in stream.getvalue()
    assert "request-key" not in stream.getvalue()
    assert {json.loads(line)["event_name"] for line in stream.getvalue().splitlines()} == {
        "context_source.created",
        "context_source_version.created",
        "job.queued",
    }


def test_same_key_and_text_replays_while_different_text_conflicts() -> None:
    unit_of_work = FakeIngestionUnitOfWork()
    service = CreateTextContextUseCase(lambda: unit_of_work, _logger(StringIO()))
    context = _context()
    command = CreateTextContextCommand(
        project_id=uuid4(),
        raw_text="same",
        idempotency_key="key",
        correlation_id=uuid4(),
    )

    first = _execute(service, context, command)
    replay = _execute(service, context, command)
    assert replay == first
    assert len(unit_of_work.context_adapter.sources) == 1
    assert len(unit_of_work.job_adapter.rows) == 1

    with pytest.raises(TextContextIdempotencyConflict):
        _execute(
            service,
            context,
            CreateTextContextCommand(
                project_id=command.project_id,
                raw_text="different",
                idempotency_key="key",
                correlation_id=uuid4(),
            ),
        )


def test_same_key_and_text_for_a_different_project_conflicts() -> None:
    unit_of_work = FakeIngestionUnitOfWork()
    service = CreateTextContextUseCase(lambda: unit_of_work, _logger(StringIO()))
    context = _context()
    first_project_id = uuid4()

    _execute(
        service,
        context,
        CreateTextContextCommand(
            project_id=first_project_id,
            raw_text="same",
            idempotency_key="key",
            correlation_id=uuid4(),
        ),
    )

    with pytest.raises(TextContextIdempotencyConflict):
        _execute(
            service,
            context,
            CreateTextContextCommand(
                project_id=uuid4(),
                raw_text="same",
                idempotency_key="key",
                correlation_id=uuid4(),
            ),
        )


def test_missing_project_does_not_commit_ingestion() -> None:
    unit_of_work = FakeIngestionUnitOfWork(project_exists=False)
    service = CreateTextContextUseCase(lambda: unit_of_work, _logger(StringIO()))
    context = _context()
    with pytest.raises(TextContextNotFound):
        _execute(
            service,
            context,
            CreateTextContextCommand(
                project_id=uuid4(),
                raw_text="valid",
                idempotency_key="key",
                correlation_id=uuid4(),
            ),
        )
    assert unit_of_work.commits == 0
    assert not unit_of_work.context_adapter.sources
    assert not unit_of_work.job_adapter.rows
