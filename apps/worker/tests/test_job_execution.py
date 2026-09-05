from __future__ import annotations

import asyncio
import json
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import create_event_logger

from app.application.job_execution import JobExecutionContext, JobExecutionCoordinator
from app.application.ports import ExecutionAcquisition


class FakeJobExecutionGuard:
    def __init__(self, *, acquisitions: list[ExecutionAcquisition]) -> None:
        self.acquisitions = acquisitions
        self.acquired: list[UUID] = []
        self.completed: list[UUID] = []

    async def acquire(self, job_id: UUID) -> ExecutionAcquisition:
        acquisition = self.acquisitions.pop(0)
        if acquisition == "acquired":
            self.acquired.append(job_id)
        return acquisition

    async def complete(self, job_id: UUID) -> None:
        self.completed.append(job_id)


class RecoverableFakeGuard(FakeJobExecutionGuard):
    def recover_interrupted(self) -> None:
        self.acquisitions.insert(0, "acquired")


def _context() -> JobExecutionContext:
    return JobExecutionContext(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        task_type="context_source_parse",
    )


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_duplicate_delivery_is_suppressed_without_handler_execution() -> None:
    context = _context()
    guard = FakeJobExecutionGuard(acquisitions=["already_in_progress"])
    stream = StringIO()
    coordinator = JobExecutionCoordinator(guard, _logger(stream))
    calls = 0

    async def handler() -> None:
        nonlocal calls
        calls += 1

    asyncio.run(coordinator.execute(context, handler))
    assert calls == 0
    assert guard.acquired == []
    assert guard.completed == []
    event = json.loads(stream.getvalue())
    assert event["event_name"] == "worker.job_duplicate_suppressed"
    assert event["job_id"] == str(context.job_id)
    assert event["account_id"] == str(context.account_id)
    assert event["project_id"] == str(context.project_id)
    assert event["task_type"] == context.task_type


def test_completed_duplicate_is_a_successful_noop() -> None:
    context = _context()
    guard = FakeJobExecutionGuard(acquisitions=["already_completed"])
    stream = StringIO()
    coordinator = JobExecutionCoordinator(guard, _logger(stream))
    calls = 0

    async def handler() -> None:
        nonlocal calls
        calls += 1

    result = asyncio.run(coordinator.execute(context, handler))
    assert result == "already_completed"
    assert calls == 0
    assert guard.completed == []
    assert json.loads(stream.getvalue())["event_name"] == "worker.job_already_completed"


def test_acquired_execution_completes_guard_after_handler() -> None:
    context = _context()
    guard = FakeJobExecutionGuard(acquisitions=["acquired"])
    stream = StringIO()
    coordinator = JobExecutionCoordinator(guard, _logger(stream))
    calls = 0

    async def handler() -> None:
        nonlocal calls
        calls += 1

    result = asyncio.run(coordinator.execute(context, handler))
    assert result == "acquired"
    assert calls == 1
    assert guard.acquired == [context.job_id]
    assert guard.completed == [context.job_id]
    assert [json.loads(line)["event_name"] for line in stream.getvalue().splitlines()] == [
        "worker.job_guard_acquired",
        "worker.job_execution_started",
    ]


def test_interrupted_execution_does_not_complete_guard_and_is_recoverable_by_fixture() -> None:
    context = _context()
    guard = RecoverableFakeGuard(acquisitions=["acquired", "already_in_progress"])
    stream = StringIO()
    coordinator = JobExecutionCoordinator(guard, _logger(stream))

    async def interrupted_handler() -> None:
        raise RuntimeError("interrupted fixture")

    with pytest.raises(RuntimeError):
        asyncio.run(coordinator.execute(context, interrupted_handler))
    assert guard.completed == []
    assert '"event_name":"worker.job_execution_interrupted"' in stream.getvalue()

    guard.recover_interrupted()
    calls = 0

    async def recovery_handler() -> None:
        nonlocal calls
        calls += 1

    assert asyncio.run(coordinator.execute(context, recovery_handler)) == "acquired"
    assert calls == 1
    assert guard.completed == [context.job_id]
