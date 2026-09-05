from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    IdempotencyConflictError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.modules.context.application.text_context_ingestion import (
    CreateTextContextCommand,
    CreateTextContextUseCase,
    TextContextIdempotencyConflict,
    TextContextNotFound,
    TextContextPermissionDenied,
)
from app.modules.context.domain.context_source import ContextSourceValidationError
from app.modules.identity.application.tenant_context import TenantContext


class CreateTextContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["text"]
    raw_text: str


class TextContextAcceptedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    status: Literal["uploaded"]
    job_id: UUID


class TextContextAcceptedMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class TextContextAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TextContextAcceptedData
    meta: TextContextAcceptedMeta


def _text_context_use_case(request: Request) -> CreateTextContextUseCase:
    return cast(CreateTextContextUseCase, request.app.state.text_context_use_case)


def create_context_sources_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/context-sources", tags=["context"])

    @router.post(
        "",
        response_model=TextContextAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_text_context(
        project_id: UUID,
        body: CreateTextContextRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        use_case: Annotated[CreateTextContextUseCase, Depends(_text_context_use_case)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> TextContextAcceptedResponse:
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Text Context ingestion requires an active request context")
        try:
            accepted = await use_case.execute(
                context,
                CreateTextContextCommand(
                    project_id=project_id,
                    raw_text=body.raw_text,
                    idempotency_key=idempotency_key,
                    correlation_id=UUID(trace.correlation_id),
                ),
            )
        except TextContextIdempotencyConflict:
            raise IdempotencyConflictError from None
        except TextContextNotFound:
            raise ResourceNotFoundError from None
        except TextContextPermissionDenied:
            raise MembershipRequiredError from None
        except (ContextSourceValidationError, ValueError):
            raise ValidationFailedError from None
        return TextContextAcceptedResponse(
            data=TextContextAcceptedData(
                source_id=accepted.source_id,
                status="uploaded",
                job_id=accepted.job_id,
            ),
            meta=TextContextAcceptedMeta(request_id=UUID(trace.request_id)),
        )

    return router
