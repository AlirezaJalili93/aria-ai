from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.jobs.application.ports import JobsRepositoryError, JobsUnitOfWorkFactory
from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent


@dataclass(frozen=True, slots=True)
class ScheduleJobCommand:
    account_id: UUID | None
    project_id: UUID | None
    job_type: str
    payload_ref: dict[str, object] | None
    idempotency_key: str | None
    correlation_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    event_payload: dict[str, object]
    max_attempts: int


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    job: Job
    outbox_event: OutboxEvent


class ScheduleJobUseCase:
    def __init__(
        self,
        unit_of_work_factory: JobsUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(self, command: ScheduleJobCommand) -> ScheduledJob:
        started_at = perf_counter()
        available_at = self._clock()
        job_id = self._id_factory()
        event_id = self._id_factory()
        enrich_trace_context(
            account_id=str(command.account_id) if command.account_id else None,
            project_id=str(command.project_id) if command.project_id else None,
            job_id=str(job_id),
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                job = await unit_of_work.jobs.add(
                    NewJob(
                        id=job_id,
                        account_id=command.account_id,
                        project_id=command.project_id,
                        job_type=command.job_type,
                        status="queued",
                        payload_ref=command.payload_ref,
                        attempt_count=0,
                        max_attempts=command.max_attempts,
                        idempotency_key=command.idempotency_key,
                        correlation_id=command.correlation_id,
                        available_at=available_at,
                    )
                )
                outbox_event = await unit_of_work.outbox.add(
                    NewOutboxEvent(
                        id=event_id,
                        account_id=command.account_id,
                        aggregate_type=command.aggregate_type,
                        aggregate_id=command.aggregate_id,
                        event_type=command.event_type,
                        payload=command.event_payload,
                        status="pending",
                        attempt_count=0,
                        available_at=available_at,
                    )
                )
                await unit_of_work.commit()
        except JobsRepositoryError:
            self._event_logger.emit(
                "job.schedule_failed",
                level="ERROR",
                component="jobs_repository",
                operation="schedule",
                error_code="JOBS_REPOSITORY_FAILURE",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
            )
            raise
        self._event_logger.emit(
            "job.queued",
            duration_ms=(perf_counter() - started_at) * 1000,
            status=job.status,
        )
        return ScheduledJob(job=job, outbox_event=outbox_event)
