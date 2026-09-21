from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.context.application.context_structuring_job_ports import (
    ContextStructuringJobRepositoryError,
    ContextStructuringJobUnitOfWorkFactory,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

CONTEXT_STRUCTURING_ROUTE_KEY = "POST /api/v1/projects/{project_id}/context-structuring"
CONTEXT_STRUCTURING_JOB_TYPE = "context_structuring"
CONTEXT_STRUCTURING_EVENT_TYPE = "context.structuring_requested.v1"
CONTEXT_STRUCTURING_PAYLOAD_VERSION = "1"
CONTEXT_STRUCTURING_IDEMPOTENCY_TTL = timedelta(hours=24)
CONTEXT_STRUCTURING_AUTOMATIC_QUEUE_RETRY = False
CONTEXT_STRUCTURING_JOB_MAX_ATTEMPTS = 1


class ContextStructuringProjectNotFound(Exception):
    """The tenant-scoped active Project is not visible."""


class ContextStructuringReadySourceRequired(Exception):
    """AI-01 cannot be scheduled without a ready non-deleted Source."""


class ContextStructuringIdempotencyConflict(Exception):
    """An idempotency key was reused for another Project command."""


class ContextStructuringPermissionDenied(Exception):
    """Only an active Membership may schedule the future command."""


@dataclass(frozen=True, slots=True)
class ScheduleContextStructuringCommand:
    project_id: UUID
    idempotency_key: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class ContextStructuringAccepted:
    job_id: UUID
    status_url: str


class ScheduleContextStructuringUseCase:
    """Internal AI-01 scheduler; no public route composes it in Increment 0071."""

    def __init__(
        self,
        unit_of_work_factory: ContextStructuringJobUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(
        self,
        context: TenantContext,
        command: ScheduleContextStructuringCommand,
    ) -> ContextStructuringAccepted:
        if context.membership_status != "active":
            raise ContextStructuringPermissionDenied
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")

        now = self._clock()
        job_id = self._id_factory()
        outbox_event_id = self._id_factory()
        idempotency_id = self._id_factory()
        request_hash = _command_hash(command.project_id)
        started_at = perf_counter()
        enrich_trace_context(
            account_id=str(context.account_id),
            project_id=str(command.project_id),
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=idempotency_id,
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=CONTEXT_STRUCTURING_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + CONTEXT_STRUCTURING_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ContextStructuringIdempotencyConflict
                    return self._replay(reservation.response_status, reservation.response_ref)

                project = await unit_of_work.projects.get(
                    account_id=context.account_id,
                    project_id=command.project_id,
                )
                if project is None:
                    raise ContextStructuringProjectNotFound
                if not await unit_of_work.readiness.has_ready_source(
                    account_id=context.account_id,
                    project_id=command.project_id,
                ):
                    raise ContextStructuringReadySourceRequired

                await unit_of_work.jobs.add(
                    NewJob(
                        id=job_id,
                        account_id=context.account_id,
                        project_id=command.project_id,
                        job_type=CONTEXT_STRUCTURING_JOB_TYPE,
                        status="queued",
                        payload_ref=None,
                        attempt_count=0,
                        max_attempts=CONTEXT_STRUCTURING_JOB_MAX_ATTEMPTS,
                        idempotency_key=command.idempotency_key,
                        correlation_id=command.correlation_id,
                        available_at=now,
                    )
                )
                await unit_of_work.outbox.add(
                    NewOutboxEvent(
                        id=outbox_event_id,
                        account_id=context.account_id,
                        aggregate_type="project",
                        aggregate_id=command.project_id,
                        event_type=CONTEXT_STRUCTURING_EVENT_TYPE,
                        delivery_channel="job_queue",
                        payload={
                            "jobId": str(job_id),
                            "taskType": CONTEXT_STRUCTURING_JOB_TYPE,
                            "payloadVersion": CONTEXT_STRUCTURING_PAYLOAD_VERSION,
                        },
                        status="pending",
                        attempt_count=0,
                        available_at=now,
                    )
                )
                accepted = ContextStructuringAccepted(
                    job_id=job_id,
                    status_url=_status_url(job_id),
                )
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=CONTEXT_STRUCTURING_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=202,
                    response_ref={
                        "job_id": str(job_id),
                        "status_url": _status_url(job_id),
                    },
                )
                await unit_of_work.commit()
        except ContextStructuringJobRepositoryError:
            self._event_logger.emit(
                "context.structuring_schedule_failed",
                level="ERROR",
                actor_id=str(context.subject_id),
                component="context_structuring_jobs",
                operation="schedule",
                error_code="CONTEXT_STRUCTURING_SCHEDULE_FAILED",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
            )
            raise

        enrich_trace_context(job_id=str(job_id))
        self._event_logger.emit(
            "job.queued",
            actor_id=str(context.subject_id),
            task_type=CONTEXT_STRUCTURING_JOB_TYPE,
            status="queued",
        )
        return accepted

    @staticmethod
    def _replay(
        response_status: int | None,
        response_ref: dict[str, object] | None,
    ) -> ContextStructuringAccepted:
        if response_status != 202 or response_ref is None:
            raise ContextStructuringJobRepositoryError
        try:
            job_id = UUID(str(response_ref["job_id"]))
            status_url = str(response_ref["status_url"])
            if set(response_ref) != {"job_id", "status_url"}:
                raise ValueError
            if status_url != _status_url(job_id):
                raise ValueError
            return ContextStructuringAccepted(job_id=job_id, status_url=status_url)
        except (KeyError, TypeError, ValueError):
            raise ContextStructuringJobRepositoryError from None


def _command_hash(project_id: UUID) -> str:
    canonical = json.dumps(
        {
            "operation": CONTEXT_STRUCTURING_JOB_TYPE,
            "project_id": str(project_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _status_url(job_id: UUID) -> str:
    return f"/api/v1/jobs/{job_id}"
