from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    ContextReadySourceRequiredError,
    ContextStructuringInProgressError,
    FeatureNotEnabledError,
    IdempotencyConflictError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.modules.context.application.context_structuring_job_ports import (
    ContextStructuringActiveJobConflict,
    ContextStructuringJobRepositoryError,
)
from app.modules.context.application.context_structuring_jobs import (
    ContextStructuringIdempotencyConflict,
    ContextStructuringPermissionDenied,
    ContextStructuringProjectNotFound,
    ContextStructuringReadySourceRequired,
    ContextStructuringSyntheticFixtureRequired,
    ScheduleContextStructuringCommand,
    ScheduleContextStructuringUseCase,
)
from app.modules.identity.application.tenant_context import TenantContext


class ContextStructuringAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status_url: str


def _context_structuring_use_case(
    request: Request,
) -> ScheduleContextStructuringUseCase | None:
    return cast(
        ScheduleContextStructuringUseCase | None,
        request.app.state.context_structuring_use_case,
    )


def create_context_structuring_router(*, enabled: bool) -> APIRouter:
    router = APIRouter(tags=["context"])

    @router.post(
        "/projects/{project_id}/context-structuring",
        response_model=ContextStructuringAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def schedule_context_structuring(
        request: Request,
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        use_case: Annotated[
            ScheduleContextStructuringUseCase | None,
            Depends(_context_structuring_use_case),
        ],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ContextStructuringAcceptedResponse:
        if not enabled or use_case is None:
            raise FeatureNotEnabledError
        if await request.body() != b"":
            raise ValidationFailedError
        trace = current_trace_context()
        if trace is None or trace.correlation_id is None:
            raise RuntimeError("Context Structuring requires an active correlation context")
        try:
            accepted = await use_case.execute(
                context,
                ScheduleContextStructuringCommand(
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                    correlation_id=UUID(trace.correlation_id),
                ),
            )
        except ContextStructuringProjectNotFound:
            raise ResourceNotFoundError from None
        except ContextStructuringIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ContextStructuringActiveJobConflict:
            raise ContextStructuringInProgressError from None
        except ContextStructuringReadySourceRequired:
            raise ContextReadySourceRequiredError from None
        except ContextStructuringPermissionDenied:
            raise MembershipRequiredError from None
        except ContextStructuringSyntheticFixtureRequired:
            raise FeatureNotEnabledError from None
        except ValueError:
            raise ValidationFailedError from None
        except ContextStructuringJobRepositoryError:
            raise
        return ContextStructuringAcceptedResponse(
            job_id=accepted.job_id,
            status_url=accepted.status_url,
        )

    return router
