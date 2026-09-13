from __future__ import annotations

import asyncio
from io import StringIO
from uuid import UUID, uuid4

from aria_observability import create_event_logger

from app.application.job_execution import JobExecutionContext, JobExecutionCoordinator


class Guard:
    async def acquire(self, job_id: UUID) -> str:
        del job_id
        return "acquired"

    async def complete(self, job_id: UUID) -> None:
        del job_id


class ExplodingMetrics:
    def record_worker_job(self, **fields: object) -> None:
        del fields
        raise RuntimeError("telemetry unavailable")


def test_telemetry_failure_does_not_fail_worker_job() -> None:
    coordinator = JobExecutionCoordinator(
        Guard(),  # type: ignore[arg-type]
        create_event_logger(
            service="aria-worker",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        ),
        ExplodingMetrics(),  # type: ignore[arg-type]
    )
    context = JobExecutionContext(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        task_type="context_parse",
    )
    calls = 0

    async def handler() -> None:
        nonlocal calls
        calls += 1

    result = asyncio.run(coordinator.execute(context, handler))
    assert result == "acquired"
    assert calls == 1

