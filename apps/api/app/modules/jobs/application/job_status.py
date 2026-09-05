from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aria_observability import enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.application.ports import JobsUnitOfWorkFactory
from app.modules.jobs.domain.job import Job, JobStatus


class JobNotFound(Exception):
    """The tenant-scoped Job was not found."""


@dataclass(frozen=True, slots=True)
class JobStatusError:
    code: str
    detail: str | None


@dataclass(frozen=True, slots=True)
class JobStatusView:
    id: UUID
    job_type: str
    status: JobStatus
    progress_stage: str | None
    retryable: bool
    error: JobStatusError | None


class JobStatusApplicationService:
    def __init__(self, unit_of_work_factory: JobsUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def get(self, context: TenantContext, job_id: UUID) -> JobStatusView:
        enrich_trace_context(account_id=str(context.account_id), job_id=str(job_id))
        async with self._unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.jobs.get_for_account(
                account_id=context.account_id,
                job_id=job_id,
            )
        if job is None:
            raise JobNotFound
        return _to_status_view(job)


def _to_status_view(job: Job) -> JobStatusView:
    error = (
        JobStatusError(code=job.error_code, detail=job.error_detail)
        if job.error_code is not None
        else None
    )
    return JobStatusView(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        # The approved Job persistence model has no progress-stage field.
        progress_stage=None,
        # Retry classification is deferred; failed Jobs are not retryable by default.
        retryable=False,
        error=error,
    )
