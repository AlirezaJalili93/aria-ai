from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    MembershipRequiredError,
    ResourceNotFoundError,
    ScopeDraftStaleError,
    ValidationFailedError,
    VersionConflictError,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_draft_service import (
    ScopeDraftAccessNotFound,
    ScopeDraftEditConflict,
    ScopeDraftPermissionDenied,
    ScopeDraftService,
    ScopeDraftStale,
    UpdateScopeSectionCommand,
)
from app.modules.scope.domain.scope_draft import ScopeDraft, ScopeDraftValidationError

ScopeSectionId = Literal[
    "summary",
    "goals",
    "pages_sections",
    "requirements",
    "content",
    "visual_direction",
    "constraints",
    "assumptions",
    "resolved_gaps",
    "remaining_non_blocking_gaps",
    "out_of_scope",
    "acceptance_notes",
]


class ScopeDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    context_version: int
    content: dict[str, object]
    updated_at: datetime


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class ScopeDraftEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ScopeDraftResponse
    meta: ResponseMeta


class UpdateScopeSectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: object
    expected_updated_at: datetime


def _service(request: Request) -> ScopeDraftService:
    return cast(ScopeDraftService, request.app.state.scope_draft_service)


def create_scope_drafts_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/scope/draft", tags=["scope"])

    @router.get("", response_model=ScopeDraftEnvelope)
    async def get_current_scope_draft(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeDraftService, Depends(_service)],
    ) -> ScopeDraftEnvelope:
        try:
            draft = await service.get_current(context, project_id=project_id)
        except ScopeDraftAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeDraftPermissionDenied:
            raise MembershipRequiredError from None
        return _envelope(draft)

    @router.patch("/sections/{section_id}", response_model=ScopeDraftEnvelope)
    async def update_scope_section(
        project_id: UUID,
        section_id: ScopeSectionId,
        body: UpdateScopeSectionRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeDraftService, Depends(_service)],
    ) -> ScopeDraftEnvelope:
        try:
            draft = await service.update_section(
                context,
                project_id=project_id,
                section_id=section_id,
                command=UpdateScopeSectionCommand(
                    value=body.value,
                    expected_updated_at=body.expected_updated_at,
                ),
            )
        except ScopeDraftAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeDraftPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeDraftEditConflict:
            raise VersionConflictError from None
        except ScopeDraftStale:
            raise ScopeDraftStaleError from None
        except ScopeDraftValidationError:
            raise ValidationFailedError from None
        return _envelope(draft)

    return router


def _envelope(draft: ScopeDraft) -> ScopeDraftEnvelope:
    return ScopeDraftEnvelope(
        data=ScopeDraftResponse(
            id=draft.id,
            context_version=draft.context_version,
            content=draft.content,
            updated_at=draft.updated_at,
        ),
        meta=ResponseMeta(request_id=_request_id()),
    )


def _request_id() -> UUID:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Scope Draft API requires an active request context")
    return UUID(trace.request_id)
