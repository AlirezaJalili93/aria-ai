from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.context_structuring_jobs import (
    CONTEXT_STRUCTURING_EVENT_TYPE,
    CONTEXT_STRUCTURING_JOB_TYPE,
    ContextStructuringIdempotencyConflict,
    ContextStructuringReadySourceRequired,
    ScheduleContextStructuringCommand,
    ScheduleContextStructuringUseCase,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.shared.idempotency import IdempotencyReservation


class _Projects:
    project: object | None = object()

    async def get(self, **_: object) -> object | None:
        return self.project


class _Readiness:
    ready = True

    async def has_ready_source(self, **_: object) -> bool:
        return self.ready


class _Jobs:
    def __init__(self) -> None:
        self.values: list[object] = []

    async def add(self, job: object) -> object:
        self.values.append(job)
        return job


class _Outbox:
    def __init__(self) -> None:
        self.values: list[object] = []

    async def add(self, event: object) -> object:
        self.values.append(event)
        return event


class _Idempotency:
    def __init__(self) -> None:
        self.reservation = IdempotencyReservation(True, "", None, None)
        self.completed: dict[str, object] | None = None

    async def reserve(self, **kwargs: object) -> IdempotencyReservation:
        if not self.reservation.acquired and not self.reservation.request_hash:
            return IdempotencyReservation(
                False,
                str(kwargs["request_hash"]),
                self.reservation.response_status,
                self.reservation.response_ref,
            )
        return self.reservation

    async def complete(self, **kwargs: object) -> None:
        self.completed = kwargs


class _UnitOfWork:
    def __init__(self) -> None:
        self.projects = _Projects()
        self.readiness = _Readiness()
        self.jobs = _Jobs()
        self.outbox = _Outbox()
        self.idempotency = _Idempotency()
        self.committed = False

    async def __aenter__(self) -> _UnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.committed = True


def _context() -> TenantContext:
    return TenantContext(
        subject_id=uuid4(),
        account_id=uuid4(),
        membership_id=uuid4(),
        role="owner",
        membership_status="active",
    )


def _service(unit_of_work: _UnitOfWork, identifiers: list[UUID]):
    iterator = iter(identifiers)
    return ScheduleContextStructuringUseCase(
        lambda: unit_of_work,  # type: ignore[arg-type]
        create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
        ),
        id_factory=lambda: next(iterator),
        clock=lambda: datetime(2026, 9, 21, tzinfo=UTC),
    )


def _run(awaitable):
    with bind_trace_context(TraceContext(correlation_id=str(uuid4()))):
        return asyncio.run(awaitable)


def test_scheduler_persists_exact_job_outbox_and_idempotency_contract() -> None:
    unit_of_work = _UnitOfWork()
    job_id, event_id, idempotency_id = uuid4(), uuid4(), uuid4()
    context = _context()
    project_id = uuid4()
    service = _service(unit_of_work, [job_id, event_id, idempotency_id])

    accepted = _run(
        service.execute(
            context,
            ScheduleContextStructuringCommand(project_id, "schedule-key", uuid4()),
        )
    )

    assert accepted.job_id == job_id
    assert accepted.status_url == f"/api/v1/jobs/{job_id}"
    job = unit_of_work.jobs.values[0]
    assert job.job_type == CONTEXT_STRUCTURING_JOB_TYPE
    assert job.payload_ref is None
    assert job.max_attempts == 1
    event = unit_of_work.outbox.values[0]
    assert event.event_type == CONTEXT_STRUCTURING_EVENT_TYPE
    assert event.delivery_channel == "job_queue"
    assert event.payload == {
        "jobId": str(job_id),
        "taskType": CONTEXT_STRUCTURING_JOB_TYPE,
        "payloadVersion": "1",
    }
    assert unit_of_work.committed is True
    assert unit_of_work.idempotency.completed is not None


def test_scheduler_exact_replay_creates_no_second_job_or_event() -> None:
    unit_of_work = _UnitOfWork()
    replay_job_id = uuid4()
    unit_of_work.idempotency.reservation = IdempotencyReservation(
        False,
        "",
        202,
        {
            "job_id": str(replay_job_id),
            "status_url": f"/api/v1/jobs/{replay_job_id}",
        },
    )
    service = _service(unit_of_work, [uuid4(), uuid4(), uuid4()])

    accepted = _run(
        service.execute(
            _context(),
            ScheduleContextStructuringCommand(uuid4(), "same-key", uuid4()),
        )
    )

    assert accepted.job_id == replay_job_id
    assert unit_of_work.jobs.values == []
    assert unit_of_work.outbox.values == []


def test_scheduler_rejects_conflicting_reuse_and_missing_ready_source() -> None:
    conflict = _UnitOfWork()
    conflict.idempotency.reservation = IdempotencyReservation(False, "different", 202, {})
    with pytest.raises(ContextStructuringIdempotencyConflict):
        _run(
            _service(conflict, [uuid4(), uuid4(), uuid4()]).execute(
                _context(),
                ScheduleContextStructuringCommand(uuid4(), "reused", uuid4()),
            )
        )

    missing = _UnitOfWork()
    missing.readiness.ready = False
    with pytest.raises(ContextStructuringReadySourceRequired):
        _run(
            _service(missing, [uuid4(), uuid4(), uuid4()]).execute(
                _context(),
                ScheduleContextStructuringCommand(uuid4(), "new", uuid4()),
            )
        )
