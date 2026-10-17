from __future__ import annotations

import base64
import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    ContextVersionRequiredError,
    IdempotencyConflictError,
    InvalidRequirementStateError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.requirements.application.requirement_crud_service import (
    CreateManualRequirementCommand,
    RequirementContextRequired,
    RequirementCrudService,
    RequirementIdempotencyConflict,
    RequirementInvalidState,
    RequirementNotFound,
    RequirementPermissionDenied,
    RequirementVersionConflict,
    UpdateRequirementCommand,
)
from app.modules.requirements.domain.requirement import (
    Requirement,
    RequirementCategory,
    RequirementCreatorType,
    RequirementPriority,
    RequirementSourceReference,
    RequirementStatus,
    RequirementValidationError,
)


class RequirementSourceReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None


class RequirementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    context_version: int
    category: RequirementCategory
    title: str = Field(max_length=255)
    description: str
    priority: RequirementPriority
    status: RequirementStatus
    source_refs: list[RequirementSourceReferenceResponse]
    confidence: Decimal | None
    is_unsupported: bool
    created_by_type: RequirementCreatorType
    acceptance_note: str | None
    created_at: datetime
    updated_at: datetime


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class CollectionMeta(ResponseMeta):
    next_cursor: str | None
    has_more: bool


class RequirementEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RequirementResponse
    meta: ResponseMeta


class RequirementsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[RequirementResponse]
    meta: CollectionMeta


class CreateManualRequirementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    category: RequirementCategory
    priority: RequirementPriority


class UpdateRequirementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: datetime
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    priority: RequirementPriority | None = None
    status: Literal["confirmed"] | None = None
    acceptance_note: str | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> UpdateRequirementRequest:
        mutable = {
            "title",
            "description",
            "priority",
            "status",
            "acceptance_note",
        }
        sent = self.model_fields_set.intersection(mutable)
        if not sent:
            raise ValueError("At least one Requirement field must be updated")
        for required_text in ("title", "description"):
            if required_text in sent and getattr(self, required_text) is None:
                raise ValueError(f"{required_text} cannot be null")
        if "priority" in sent and self.priority is None:
            raise ValueError("priority cannot be null")
        if "status" in sent and self.status is None:
            raise ValueError("status cannot be null")
        return self


def _requirement_service(request: Request) -> RequirementCrudService:
    return cast(RequirementCrudService, request.app.state.requirement_crud_service)


def create_requirements_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])

    @router.get("", response_model=RequirementsResponse)
    async def list_requirements(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[RequirementCrudService, Depends(_requirement_service)],
        category: Annotated[RequirementCategory | None, Query()] = None,
        status_filter: Annotated[RequirementStatus | None, Query(alias="status")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> RequirementsResponse:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        try:
            rows = await service.list(
                context,
                project_id=project_id,
                category=category,
                status=status_filter,
                limit=limit + 1,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
            )
        except RequirementNotFound:
            raise ResourceNotFoundError from None
        except RequirementPermissionDenied:
            raise MembershipRequiredError from None
        has_more = len(rows) > limit
        page = rows[:limit]
        return RequirementsResponse(
            data=[_response(item) for item in page],
            meta=CollectionMeta(
                request_id=_request_id(),
                next_cursor=_encode_cursor(page[-1]) if has_more and page else None,
                has_more=has_more,
            ),
        )

    @router.post("", response_model=RequirementEnvelope, status_code=status.HTTP_201_CREATED)
    async def create_manual_requirement(
        project_id: UUID,
        body: CreateManualRequirementRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[RequirementCrudService, Depends(_requirement_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> RequirementEnvelope:
        try:
            requirement = await service.create_manual(
                context,
                project_id=project_id,
                command=CreateManualRequirementCommand(
                    title=body.title,
                    description=body.description,
                    category=body.category,
                    priority=body.priority,
                    idempotency_key=idempotency_key,
                ),
            )
        except RequirementNotFound:
            raise ResourceNotFoundError from None
        except RequirementContextRequired:
            raise ContextVersionRequiredError from None
        except RequirementIdempotencyConflict:
            raise IdempotencyConflictError from None
        except RequirementPermissionDenied:
            raise MembershipRequiredError from None
        except (RequirementValidationError, ValueError):
            raise ValidationFailedError from None
        return RequirementEnvelope(
            data=_response(requirement), meta=ResponseMeta(request_id=_request_id())
        )

    @router.patch("/{requirement_id}", response_model=RequirementEnvelope)
    async def update_requirement(
        project_id: UUID,
        requirement_id: UUID,
        body: UpdateRequirementRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[RequirementCrudService, Depends(_requirement_service)],
    ) -> RequirementEnvelope:
        try:
            requirement = await service.update(
                context,
                project_id=project_id,
                requirement_id=requirement_id,
                command=UpdateRequirementCommand(
                    expected_updated_at=body.expected_updated_at,
                    title=body.title,
                    description=body.description,
                    priority=body.priority,
                    status=body.status,
                    acceptance_note=body.acceptance_note,
                    acceptance_note_set="acceptance_note" in body.model_fields_set,
                ),
            )
        except RequirementNotFound:
            raise ResourceNotFoundError from None
        except RequirementPermissionDenied:
            raise MembershipRequiredError from None
        except RequirementVersionConflict:
            raise VersionConflictError from None
        except RequirementInvalidState:
            raise InvalidRequirementStateError from None
        except (RequirementValidationError, ValueError):
            raise ValidationFailedError from None
        return RequirementEnvelope(
            data=_response(requirement), meta=ResponseMeta(request_id=_request_id())
        )

    @router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_requirement(
        project_id: UUID,
        requirement_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[RequirementCrudService, Depends(_requirement_service)],
    ) -> Response:
        try:
            await service.remove_draft(
                context,
                project_id=project_id,
                requirement_id=requirement_id,
            )
        except RequirementNotFound:
            raise ResourceNotFoundError from None
        except RequirementPermissionDenied:
            raise MembershipRequiredError from None
        except RequirementVersionConflict:
            raise VersionConflictError from None
        except RequirementInvalidState:
            raise InvalidRequirementStateError from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _response(requirement: Requirement) -> RequirementResponse:
    return RequirementResponse(
        id=requirement.id,
        context_version=requirement.context_version,
        category=requirement.category,
        title=requirement.title,
        description=requirement.description,
        priority=requirement.priority,
        status=requirement.status,
        source_refs=[_source_response(value) for value in requirement.source_refs],
        confidence=requirement.confidence,
        is_unsupported=requirement.is_unsupported,
        created_by_type=requirement.created_by_type,
        acceptance_note=requirement.acceptance_note,
        created_at=requirement.created_at,
        updated_at=requirement.updated_at,
    )


def _source_response(
    value: RequirementSourceReference,
) -> RequirementSourceReferenceResponse:
    return RequirementSourceReferenceResponse(
        source_id=value.source_id,
        source_version_id=value.source_version_id,
        start_offset=value.start_offset,
        end_offset=value.end_offset,
    )


def _request_id() -> UUID:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Requirement API requires an active request context")
    return UUID(trace.request_id)


def _encode_cursor(requirement: Requirement) -> str:
    raw = json.dumps(
        {"created_at": requirement.created_at.isoformat(), "id": str(requirement.id)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        requirement_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, requirement_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ValidationFailedError from None
