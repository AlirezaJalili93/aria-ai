from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.context.application.text_context_ingestion import (
    TEXT_CONTEXT_JOB_MAX_ATTEMPTS,
    TEXT_CONTEXT_JOB_TYPE,
)
from app.modules.context.application.text_ingestion_ports import (
    TextContextIngestionRepositoryError,
    TextContextIngestionUnitOfWorkFactory,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

JOB_RETRY_ROUTE_KEY = "POST /api/v1/jobs/{job_id}/retry"
JOB_RETRY_IDEMPOTENCY_TTL = timedelta(hours=24)
RETRYABLE_PARSER_ERROR = "PARSER_STORAGE_UNAVAILABLE"


class JobRetryNotFound(Exception):
    """The target Job or its parser aggregate is not visible in the tenant."""


class JobRetryNotAllowed(Exception):
    """The target Job does not satisfy the explicit parser retry contract."""


class JobRetryIdempotencyConflict(Exception):
    """An idempotency key was reused for a different target Job."""


@dataclass(frozen=True, slots=True)
class RetryJobCommand:
    job_id: UUID
    idempotency_key: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class RetriedJob:
    id: UUID
    status: str
    retry_of_job_id: UUID


class RetryJobUseCase:
    def __init__(
        self,
        unit_of_work_factory: TextContextIngestionUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(self, context: TenantContext, command: RetryJobCommand) -> RetriedJob:
        if context.membership_status != "active":
            raise JobRetryNotFound
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        request_hash = _request_hash(command.job_id)
        now = self._clock()
        started_at = perf_counter()
        enrich_trace_context(account_id=str(context.account_id), job_id=str(command.job_id))
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=self._id_factory(),
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=JOB_RETRY_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + JOB_RETRY_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise JobRetryIdempotencyConflict
                    result = _replay(reservation.response_status, reservation.response_ref)
                    self._event_logger.emit(
                        "job.retry_replayed",
                        actor_id=str(context.subject_id),
                        job_id=str(result.id),
                        retry_of_job_id=str(result.retry_of_job_id),
                        status="queued",
                    )
                    return result

                parent = await unit_of_work.jobs.get_for_account_for_update(
                    account_id=context.account_id, job_id=command.job_id
                )
                if parent is None or parent.project_id is None:
                    raise JobRetryNotFound
                if (
                    parent.job_type != TEXT_CONTEXT_JOB_TYPE
                    or parent.status != "failed"
                    or parent.error_code != RETRYABLE_PARSER_ERROR
                ):
                    raise JobRetryNotAllowed
                payload = parent.payload_ref or {}
                if set(payload) != {"source_id", "source_version_id"}:
                    raise JobRetryNotAllowed
                try:
                    source_id = UUID(str(payload["source_id"]))
                    source_version_id = UUID(str(payload["source_version_id"]))
                except (ValueError, TypeError):
                    raise JobRetryNotAllowed from None
                if (
                    await unit_of_work.jobs.get_retry_child(
                        account_id=context.account_id,
                        project_id=parent.project_id,
                        retry_of_job_id=parent.id,
                    )
                    is not None
                ):
                    raise JobRetryNotAllowed
                source = await unit_of_work.context_sources.get_source(
                    account_id=context.account_id,
                    project_id=parent.project_id,
                    source_id=source_id,
                )
                version = await unit_of_work.context_sources.get_version(
                    account_id=context.account_id,
                    project_id=parent.project_id,
                    source_id=source_id,
                    version_id=source_version_id,
                )
                if source is None or version is None:
                    raise JobRetryNotFound
                if source.status != "failed" or version.parse_status != "failed":
                    raise JobRetryNotAllowed
                if await unit_of_work.jobs.has_active_parser_job(
                    account_id=context.account_id,
                    project_id=parent.project_id,
                    source_version_id=source_version_id,
                ):
                    raise JobRetryNotAllowed

                reset = await unit_of_work.context_sources.reset_failed_for_retry(
                    account_id=context.account_id,
                    project_id=parent.project_id,
                    source_id=source_id,
                    version_id=source_version_id,
                )
                if not reset:
                    raise JobRetryNotAllowed
                child_id = self._id_factory()
                await unit_of_work.jobs.add(
                    NewJob(
                        id=child_id,
                        account_id=context.account_id,
                        project_id=parent.project_id,
                        job_type=TEXT_CONTEXT_JOB_TYPE,
                        status="queued",
                        payload_ref={
                            "source_id": str(source_id),
                            "source_version_id": str(source_version_id),
                        },
                        attempt_count=0,
                        max_attempts=TEXT_CONTEXT_JOB_MAX_ATTEMPTS,
                        idempotency_key=command.idempotency_key,
                        correlation_id=command.correlation_id,
                        available_at=now,
                    ),
                    retry_of_job_id=parent.id,
                )
                await unit_of_work.outbox.add(
                    NewOutboxEvent(
                        id=self._id_factory(),
                        account_id=context.account_id,
                        aggregate_type="context_source",
                        aggregate_id=source_id,
                        event_type="context_added.v1",
                        delivery_channel="job_queue",
                        payload={
                            "jobId": str(child_id),
                            "taskType": TEXT_CONTEXT_JOB_TYPE,
                            "payloadVersion": "1",
                            "accountId": str(context.account_id),
                            "projectId": str(parent.project_id),
                            "correlationId": str(command.correlation_id),
                        },
                        status="pending",
                        attempt_count=0,
                        available_at=now,
                    )
                )
                result = RetriedJob(id=child_id, status="queued", retry_of_job_id=parent.id)
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=JOB_RETRY_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=202,
                    response_ref={
                        "job_id": str(result.id),
                        "status": result.status,
                        "retry_of_job_id": str(result.retry_of_job_id),
                    },
                )
                await unit_of_work.commit()
        except (JobRetryNotFound, JobRetryNotAllowed, JobRetryIdempotencyConflict):
            raise
        except TextContextIngestionRepositoryError:
            self._event_logger.emit(
                "job.retry_rejected",
                level="ERROR",
                actor_id=str(context.subject_id),
                job_id=str(command.job_id),
                error_code="JOB_RETRY_REPOSITORY_FAILURE",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
            )
            raise
        enrich_trace_context(job_id=str(result.id), project_id=str(parent.project_id))
        self._event_logger.emit(
            "job.retry_queued",
            actor_id=str(context.subject_id),
            job_id=str(result.id),
            retry_of_job_id=str(parent.id),
            source_id=str(source_id),
            source_version_id=str(source_version_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="queued",
        )
        return result


def _request_hash(job_id: UUID) -> str:
    raw = json.dumps({"job_id": str(job_id)}, separators=(",", ":"), sort_keys=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def _replay(status: int | None, response: dict[str, object] | None) -> RetriedJob:
    if status != 202 or response is None:
        raise TextContextIngestionRepositoryError("Incomplete Job retry reservation")
    try:
        if response["status"] != "queued":
            raise ValueError
        return RetriedJob(
            id=UUID(str(response["job_id"])),
            status="queued",
            retry_of_job_id=UUID(str(response["retry_of_job_id"])),
        )
    except (KeyError, TypeError, ValueError):
        raise TextContextIngestionRepositoryError("Invalid Job retry snapshot") from None
