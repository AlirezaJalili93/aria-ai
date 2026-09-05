from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.jobs.application.ports import (
    JobRepository,
    JobsRepositoryError,
    JobsUnitOfWork,
    OutboxRepository,
)
from app.modules.jobs.application.schedule_job import ScheduleJobCommand, ScheduleJobUseCase
from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent


class FakeJobRepository(JobRepository):
    def __init__(self, *, fail: bool = False) -> None:
        self.rows: dict[UUID, Job] = {}
        self.fail = fail

    async def add(self, job: NewJob) -> Job:
        if self.fail:
            raise JobsRepositoryError
        row = Job(
            **asdict(job),
            started_at=None,
            finished_at=None,
            error_code=None,
            error_detail=None,
            created_at=datetime.now(UTC),
        )
        self.rows[row.id] = row
        return row

    async def get(self, job_id: UUID) -> Job | None:
        return self.rows.get(job_id)


class FakeOutboxRepository(OutboxRepository):
    def __init__(self) -> None:
        self.rows: dict[UUID, OutboxEvent] = {}

    async def add(self, event: NewOutboxEvent) -> OutboxEvent:
        row = OutboxEvent(**asdict(event), created_at=datetime.now(UTC), published_at=None)
        self.rows[row.id] = row
        return row

    async def get(self, event_id: UUID) -> OutboxEvent | None:
        return self.rows.get(event_id)


class FakeJobsUnitOfWork(JobsUnitOfWork):
    def __init__(self, jobs: FakeJobRepository, outbox: FakeOutboxRepository) -> None:
        self._jobs = jobs
        self._outbox = outbox
        self.commits = 0

    @property
    def jobs(self) -> JobRepository:
        return self._jobs

    @property
    def outbox(self) -> OutboxRepository:
        return self._outbox

    async def __aenter__(self) -> FakeJobsUnitOfWork:
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


def _command() -> ScheduleJobCommand:
    return ScheduleJobCommand(
        account_id=uuid4(),
        project_id=uuid4(),
        job_type="context_parse",
        payload_ref={"source_id": str(uuid4()), "private": "do-not-log"},
        idempotency_key="private-key",
        correlation_id=uuid4(),
        event_type="context_added.v1",
        aggregate_type="context_source",
        aggregate_id=uuid4(),
        event_payload={"private": "do-not-log"},
        max_attempts=3,
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


def test_job_and_outbox_are_persisted_before_one_commit_and_logged_safely() -> None:
    jobs = FakeJobRepository()
    outbox = FakeOutboxRepository()
    unit_of_work = FakeJobsUnitOfWork(jobs, outbox)
    stream = StringIO()
    job_id, event_id = uuid4(), uuid4()
    service = ScheduleJobUseCase(
        lambda: unit_of_work,
        _logger(stream),
        id_factory=iter((job_id, event_id)).__next__,
    )
    command = _command()

    async def scenario():
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(command.correlation_id))
        ):
            return await service.execute(command)

    result = asyncio.run(scenario())
    assert result.job.id == job_id
    assert result.outbox_event.id == event_id
    assert unit_of_work.commits == 1
    event = json.loads(stream.getvalue())
    assert event["event_name"] == "job.queued"
    assert event["job_id"] == str(job_id)
    assert event["account_id"] == str(command.account_id)
    assert event["project_id"] == str(command.project_id)
    assert "do-not-log" not in stream.getvalue()
    assert "private-key" not in stream.getvalue()


def test_repository_failure_emits_safe_failure_without_commit() -> None:
    jobs = FakeJobRepository(fail=True)
    unit_of_work = FakeJobsUnitOfWork(jobs, FakeOutboxRepository())
    stream = StringIO()
    service = ScheduleJobUseCase(lambda: unit_of_work, _logger(stream))
    command = _command()

    async def scenario() -> None:
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(command.correlation_id))
        ), pytest.raises(JobsRepositoryError):
            await service.execute(command)

    asyncio.run(scenario())
    assert unit_of_work.commits == 0
    event = json.loads(stream.getvalue())
    assert event["event_name"] == "job.schedule_failed"
    assert event["error_code"] == "JOBS_REPOSITORY_FAILURE"
    assert "do-not-log" not in stream.getvalue()
