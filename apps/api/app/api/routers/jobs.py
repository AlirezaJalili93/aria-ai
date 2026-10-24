from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    IdempotencyConflictError,
    JobNotRetryableError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.application.job_retry import (
    JobRetryIdempotencyConflict,
    JobRetryNotAllowed,
    JobRetryNotFound,
    RetriedJob,
    RetryJobCommand,
    RetryJobUseCase,
)
from app.modules.jobs.application.job_status import (
    JobNotFound,
    JobStatusApplicationService,
    JobStatusView,
)
from app.modules.jobs.domain.job import JobStatus


class JobStatusErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    detail: str | None


class JobStatusDataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job_type: str
    status: JobStatus
    progress_stage: str | None
    retryable: bool
    error: JobStatusErrorResponse | None


class JobStatusMetaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: JobStatusDataResponse
    meta: JobStatusMetaResponse


class JobRetryDataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: str
    retry_of_job_id: UUID
    status_url: str


class JobRetryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: JobRetryDataResponse
    meta: JobStatusMetaResponse


def _job_status_service(request: Request) -> JobStatusApplicationService:
    return cast(JobStatusApplicationService, request.app.state.job_status_service)


def _job_retry_use_case(request: Request) -> RetryJobUseCase:
    return cast(RetryJobUseCase, request.app.state.job_retry_use_case)


def create_jobs_router() -> APIRouter:
    router = APIRouter(prefix="/jobs", tags=["jobs"])

    @router.get("/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(
        job_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[JobStatusApplicationService, Depends(_job_status_service)],
    ) -> JobStatusResponse:
        try:
            view = await service.get(context, job_id)
        except JobNotFound:
            raise ResourceNotFoundError from None
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Job status requires an active request context")
        return JobStatusResponse(
            data=_data_response(view),
            meta=JobStatusMetaResponse(request_id=UUID(trace.request_id)),
        )

    @router.post(
        "/{job_id}/retry",
        response_model=JobRetryResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def retry_job(
        job_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        use_case: Annotated[RetryJobUseCase, Depends(_job_retry_use_case)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> JobRetryResponse:
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Job retry requires an active request context")
        try:
            retried = await use_case.execute(
                context,
                RetryJobCommand(
                    job_id=job_id,
                    idempotency_key=idempotency_key,
                    correlation_id=UUID(trace.correlation_id),
                ),
            )
        except JobRetryNotFound:
            raise ResourceNotFoundError from None
        except JobRetryNotAllowed:
            raise JobNotRetryableError from None
        except JobRetryIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ValueError:
            raise ValidationFailedError from None
        return _retry_response(retried, UUID(trace.request_id))

    return router


def _retry_response(value: RetriedJob, request_id: UUID) -> JobRetryResponse:
    return JobRetryResponse(
        data=JobRetryDataResponse(
            job_id=value.id,
            status=value.status,
            retry_of_job_id=value.retry_of_job_id,
            status_url=f"/api/v1/jobs/{value.id}",
        ),
        meta=JobStatusMetaResponse(request_id=request_id),
    )


def _data_response(view: JobStatusView) -> JobStatusDataResponse:
    return JobStatusDataResponse(
        id=view.id,
        job_type=view.job_type,
        status=view.status,
        progress_stage=view.progress_stage,
        retryable=view.retryable,
        error=(
            JobStatusErrorResponse(code=view.error.code, detail=view.error.detail)
            if view.error is not None
            else None
        ),
    )
