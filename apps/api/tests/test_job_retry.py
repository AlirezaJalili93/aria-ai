from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.ports import ContextSourceRepository
from app.modules.context.application.text_ingestion_ports import TextContextIngestionUnitOfWork
from app.modules.context.domain.context_source import ContextSource, ContextSourceVersion
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.application.job_retry import (
    JobRetryNotAllowed,
    RetryJobCommand,
    RetryJobUseCase,
)
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent
from app.modules.projects.application.ports import ProjectRepository
from app.shared.idempotency import IdempotencyRepository, IdempotencyReservation


class FakeIdempotency:
    def __init__(self) -> None:
        self.request_hash: str | None = None
        self.response_status: int | None = None
        self.response_ref: dict[str, object] | None = None

    async def reserve(self, **values) -> IdempotencyReservation:
        request_hash = cast(str, values["request_hash"])
        if self.request_hash is None:
            self.request_hash = request_hash
            return IdempotencyReservation(True, request_hash, None, None)
        return IdempotencyReservation(
            False, self.request_hash, self.response_status, self.response_ref
        )

    async def complete(self, **values) -> None:
        self.response_status = cast(int, values["response_status"])
        self.response_ref = cast(dict[str, object], values["response_ref"])


class FakeJobs:
    def __init__(self, parent: Job) -> None:
        self.parent = parent
        self.children: list[Job] = []
        self.active = False

    async def get_for_account_for_update(self, account_id: UUID, job_id: UUID) -> Job | None:
        return (
            self.parent
            if self.parent.account_id == account_id and self.parent.id == job_id
            else None
        )

    async def get_for_account(self, account_id: UUID, job_id: UUID) -> Job | None:
        return await self.get_for_account_for_update(account_id, job_id)

    async def get_retry_child(
        self, *, account_id: UUID, project_id: UUID, retry_of_job_id: UUID
    ) -> Job | None:
        return next(
            (
                row
                for row in self.children
                if row.account_id == account_id
                and row.project_id == project_id
                and row.retry_of_job_id == retry_of_job_id
            ),
            None,
        )

    async def has_active_parser_job(self, **values) -> bool:
        del values
        return self.active

    async def add(self, job: NewJob, *, retry_of_job_id: UUID | None = None) -> Job:
        persisted = Job(
            **asdict(job),
            started_at=None,
            finished_at=None,
            error_code=None,
            error_detail=None,
            created_at=datetime.now(UTC),
            retry_of_job_id=retry_of_job_id,
        )
        self.children.append(persisted)
        return persisted


class FakeContextSources:
    def __init__(self, source: ContextSource, version: ContextSourceVersion) -> None:
        self.source = source
        self.version = version

    async def get_source(self, **values) -> ContextSource | None:
        return self.source if values["source_id"] == self.source.id else None

    async def get_version(self, **values) -> ContextSourceVersion | None:
        return self.version if values["version_id"] == self.version.id else None

    async def reset_failed_for_retry(self, **values) -> bool:
        if values["source_id"] != self.source.id or values["version_id"] != self.version.id:
            return False
        if self.source.status != "failed" or self.version.parse_status != "failed":
            return False
        self.source = replace(self.source, status="uploaded")
        self.version = replace(self.version, parse_status="pending")
        return True


class FakeOutbox:
    def __init__(self) -> None:
        self.rows: list[OutboxEvent] = []

    async def add(self, event: NewOutboxEvent) -> OutboxEvent:
        row = OutboxEvent(**asdict(event), created_at=datetime.now(UTC), published_at=None)
        self.rows.append(row)
        return row


class FakeRetryUnitOfWork(TextContextIngestionUnitOfWork):
    def __init__(self, parent: Job, source: ContextSource, version: ContextSourceVersion) -> None:
        self.job_adapter = FakeJobs(parent)
        self.context_adapter = FakeContextSources(source, version)
        self.outbox_adapter = FakeOutbox()
        self.idempotency_adapter = FakeIdempotency()
        self.commits = 0

    @property
    def projects(self) -> ProjectRepository:
        return cast(ProjectRepository, object())

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

    @property
    def upload_allocations(self):
        raise AssertionError("Retry must not create an upload allocation")

    async def __aenter__(self) -> FakeRetryUnitOfWork:
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


def _fixture() -> tuple[
    RetryJobUseCase, FakeRetryUnitOfWork, TenantContext, RetryJobCommand, StringIO
]:
    now = datetime.now(UTC)
    account_id = uuid4()
    project_id = uuid4()
    actor_id = uuid4()
    source_id = uuid4()
    version_id = uuid4()
    parent_id = uuid4()
    parent = Job(
        id=parent_id,
        account_id=account_id,
        project_id=project_id,
        job_type="context_source_parse",
        status="failed",
        payload_ref={"source_id": str(source_id), "source_version_id": str(version_id)},
        attempt_count=1,
        max_attempts=1,
        idempotency_key="upload-key",
        correlation_id=uuid4(),
        available_at=now,
        started_at=now,
        finished_at=now,
        error_code="PARSER_STORAGE_UNAVAILABLE",
        error_detail=None,
        created_at=now,
    )
    source = ContextSource(
        id=source_id,
        account_id=account_id,
        project_id=project_id,
        source_type="file",
        status="failed",
        original_name="brief.txt",
        mime_type="text/plain",
        storage_ref="private/object",
        raw_text=None,
        checksum=None,
        created_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    version = ContextSourceVersion(
        id=version_id,
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_no=1,
        content_hash=None,
        canonical_text=None,
        storage_ref="private/object",
        metadata=None,
        parse_status="failed",
        created_at=now,
    )
    uow = FakeRetryUnitOfWork(parent, source, version)
    ids = iter((uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4()))
    stream = StringIO()
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    service = RetryJobUseCase(lambda: uow, logger, id_factory=lambda: next(ids))
    context = TenantContext(
        subject_id=actor_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )
    command = RetryJobCommand(job_id=parent_id, idempotency_key="retry-key", correlation_id=uuid4())
    return service, uow, context, command, stream


def _execute(service: RetryJobUseCase, context: TenantContext, command: RetryJobCommand):
    async def scenario():
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(command.correlation_id))
        ):
            return await service.execute(context, command)

    return asyncio.run(scenario())


def test_retry_creates_one_child_for_same_source_version_and_replays_same_key() -> None:
    service, uow, context, command, stream = _fixture()
    first = _execute(service, context, command)
    second = _execute(service, context, command)

    assert first == second
    assert first.retry_of_job_id == command.job_id
    assert len(uow.job_adapter.children) == 1
    assert uow.job_adapter.children[0].payload_ref == uow.job_adapter.parent.payload_ref
    assert len(uow.outbox_adapter.rows) == 1
    assert uow.context_adapter.source.status == "uploaded"
    assert uow.context_adapter.version.parse_status == "pending"
    assert uow.job_adapter.parent.status == "failed"
    assert uow.commits == 1
    logs = stream.getvalue()
    assert "job.retry_queued" in logs
    assert "job.retry_replayed" in logs
    assert "private/object" not in logs
    assert "brief.txt" not in logs


def test_retry_rejects_active_or_nonrecoverable_parser_job() -> None:
    service, uow, context, command, _ = _fixture()
    uow.job_adapter.active = True
    with pytest.raises(JobRetryNotAllowed):
        _execute(service, context, command)
    assert not uow.job_adapter.children
    assert not uow.outbox_adapter.rows

    service, uow, context, command, _ = _fixture()
    uow.job_adapter.parent = replace(uow.job_adapter.parent, error_code="PARSER_INVALID_INPUT")
    with pytest.raises(JobRetryNotAllowed):
        _execute(service, context, command)
    assert not uow.job_adapter.children
