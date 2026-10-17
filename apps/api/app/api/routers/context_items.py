from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, model_validator

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    InvalidContextItemStateError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.modules.context.application.context_item_service import (
    ContextItemInvalidState,
    ContextItemNotFound,
    ContextItemPermissionDenied,
    ContextItemReviewService,
    ContextItemVersionConflict,
    ReviewContextItemCommand,
)
from app.modules.context.domain.context_item import (
    ContextItem,
    ContextItemCreatorType,
    ContextItemStatus,
    ContextItemType,
    ContextItemValidationError,
    SourceReference,
)
from app.modules.identity.application.tenant_context import TenantContext


class SourceReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None


class ContextItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    context_version: int
    item_type: ContextItemType
    content: str
    source_refs: list[SourceReferenceResponse]
    confidence: float | None
    status: ContextItemStatus
    created_by_type: ContextItemCreatorType
    created_at: datetime
    updated_at: datetime


class CollectionMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    next_cursor: str | None
    has_more: bool


class ContextItemsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ContextItemResponse]
    meta: CollectionMeta


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class ContextItemEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ContextItemResponse
    meta: ResponseMeta


class ReviewContextItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["confirm", "reject", "edit"]
    expected_updated_at: datetime
    content: str | None = None

    @model_validator(mode="after")
    def validate_command_fields(self) -> ReviewContextItemRequest:
        content_was_sent = "content" in self.model_fields_set
        if self.command == "edit" and (not content_was_sent or self.content is None):
            raise ValueError("edit requires content")
        if self.command != "edit" and content_was_sent:
            raise ValueError("content is only accepted for edit")
        return self


def _review_service(request: Request) -> ContextItemReviewService:
    return cast(ContextItemReviewService, request.app.state.context_item_review_service)


def create_context_items_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/context-items", tags=["context"])

    @router.get("", response_model=ContextItemsResponse)
    async def list_context_items(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ContextItemReviewService, Depends(_review_service)],
        item_type: Annotated[ContextItemType | None, Query()] = None,
        status: Annotated[ContextItemStatus | None, Query()] = None,
        source_id: Annotated[UUID | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> ContextItemsResponse:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        try:
            result = await service.list_current(
                context,
                project_id=project_id,
                item_type=item_type,
                status=status,
                source_id=source_id,
                limit=limit + 1,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
            )
        except ContextItemNotFound:
            raise ResourceNotFoundError from None
        except ContextItemPermissionDenied:
            raise MembershipRequiredError from None

        has_more = len(result.items) > limit
        page = result.items[:limit]
        return ContextItemsResponse(
            data=[_response(item) for item in page],
            meta=CollectionMeta(
                request_id=_request_id(),
                next_cursor=_encode_cursor(page[-1]) if has_more and page else None,
                has_more=has_more,
            ),
        )

    @router.patch("/{item_id}", response_model=ContextItemEnvelope)
    async def review_context_item(
        project_id: UUID,
        item_id: UUID,
        body: ReviewContextItemRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ContextItemReviewService, Depends(_review_service)],
    ) -> ContextItemEnvelope:
        try:
            item = await service.review(
                context,
                project_id=project_id,
                item_id=item_id,
                command=ReviewContextItemCommand(
                    command=body.command,
                    expected_updated_at=body.expected_updated_at,
                    content=body.content,
                ),
            )
        except ContextItemNotFound:
            raise ResourceNotFoundError from None
        except ContextItemPermissionDenied:
            raise MembershipRequiredError from None
        except ContextItemVersionConflict:
            raise VersionConflictError from None
        except ContextItemInvalidState:
            raise InvalidContextItemStateError from None
        except ContextItemValidationError:
            raise ValidationFailedError from None
        return ContextItemEnvelope(
            data=_response(item),
            meta=ResponseMeta(request_id=_request_id()),
        )

    return router


def _response(item: ContextItem) -> ContextItemResponse:
    return ContextItemResponse(
        id=item.id,
        context_version=item.context_version,
        item_type=item.item_type,
        content=item.content,
        source_refs=[_source_response(value) for value in item.source_refs],
        confidence=float(item.confidence) if item.confidence is not None else None,
        status=item.status,
        created_by_type=item.created_by_type,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _source_response(value: SourceReference) -> SourceReferenceResponse:
    return SourceReferenceResponse(
        source_id=value.source_id,
        source_version_id=value.source_version_id,
        start_offset=value.start_offset,
        end_offset=value.end_offset,
    )


def _request_id() -> UUID:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Context Item API requires an active request context")
    return UUID(trace.request_id)


def _encode_cursor(item: ContextItem) -> str:
    raw = json.dumps(
        {"created_at": item.created_at.isoformat(), "id": str(item.id)},
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
        item_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, item_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ValidationFailedError from None
