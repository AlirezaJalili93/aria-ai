from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, model_validator

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    DuplicateClarificationError,
    IdempotencyConflictError,
    InvalidClarificationStateError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.modules.gaps.application.clarification_service import (
    ClarificationDuplicate,
    ClarificationIdempotencyConflict,
    ClarificationInvalidState,
    ClarificationNotFound,
    ClarificationPermissionDenied,
    ClarificationService,
    ClarificationVersionConflict,
    CreateClarificationQuestionCommand,
    DismissGapCommand,
    EditClarificationQuestionCommand,
    ResolveClarificationCommand,
)
from app.modules.gaps.domain.clarification import (
    Clarification,
    ClarificationAuthorType,
    ClarificationCreatorType,
    ClarificationResolution,
    ClarificationResolutionType,
    ClarificationStatus,
    ClarificationValidationError,
)
from app.modules.gaps.domain.gap import (
    Gap,
    GapSeverity,
    GapStatus,
    GapType,
    SuggestedResolutionType,
)
from app.modules.identity.application.tenant_context import TenantContext


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


class CollectionMeta(ResponseMeta):
    next_cursor: str | None
    has_more: bool


class GapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    context_version: int
    gap_type: GapType
    severity: GapSeverity
    status: GapStatus
    explanation: str | None
    suggested_resolution_type: SuggestedResolutionType | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class GapsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[GapResponse]
    meta: CollectionMeta


class ClarificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    gap_id: UUID
    question_text: str
    status: ClarificationStatus
    created_by_type: ClarificationCreatorType
    created_at: datetime
    updated_at: datetime


class ClarificationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ClarificationResponse
    meta: ResponseMeta


class ResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    clarification_id: UUID
    resolution_type: ClarificationResolutionType
    answer_text: str | None
    author_type: ClarificationAuthorType
    created_at: datetime


class HistoryResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    resolution_type: ClarificationResolutionType
    answer_text: str | None
    author_type: ClarificationAuthorType
    created_at: datetime


class ClarificationHistoryResponse(ClarificationResponse):
    resolution: HistoryResolutionResponse | None


class ClarificationHistoryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list[ClarificationHistoryResponse]
    meta: CollectionMeta


class ResolutionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ResolutionResponse
    meta: ResponseMeta


class CreateQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_text: str


class EditQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_text: str
    expected_updated_at: datetime


class CreateResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution_type: ClarificationResolutionType
    answer_text: str | None = None
    author_type: ClarificationAuthorType

    @model_validator(mode="after")
    def validate_answer_shape(self) -> CreateResolutionRequest:
        if self.resolution_type in {"provided_information", "internal_decision"}:
            if self.answer_text is None or not self.answer_text.strip():
                raise ValueError("answer_text is required for an answering resolution")
        elif self.answer_text is not None:
            raise ValueError("answer_text is forbidden for an action-only resolution")
        return self


def _service(request: Request) -> ClarificationService:
    return cast(ClarificationService, request.app.state.clarification_service)


def create_clarifications_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/gaps", tags=["clarifications"])

    @router.get("", response_model=GapsResponse)
    async def list_gaps(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ClarificationService, Depends(_service)],
        status_filter: Annotated[GapStatus | None, Query(alias="status")] = None,
        severity: Annotated[GapSeverity | None, Query()] = None,
        gap_type: Annotated[GapType | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> GapsResponse:
        filters = {
            "status": status_filter,
            "severity": severity,
            "gap_type": gap_type,
        }
        cursor_created_at, cursor_id = _decode_gap_cursor(cursor, filters)
        try:
            rows = await service.list_gaps(
                context,
                project_id=project_id,
                status=status_filter,
                severity=severity,
                gap_type=gap_type,
                limit=limit + 1,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
            )
        except ClarificationNotFound:
            raise ResourceNotFoundError from None
        except ClarificationPermissionDenied:
            raise MembershipRequiredError from None
        has_more = len(rows) > limit
        page = rows[:limit]
        return GapsResponse(
            data=[_gap_response(item) for item in page],
            meta=CollectionMeta(
                request_id=_request_id(),
                next_cursor=(
                    _encode_gap_cursor(page[-1], filters) if has_more and page else None
                ),
                has_more=has_more,
            ),
        )

    @router.get(
        "/{gap_id}/clarifications", response_model=ClarificationHistoryEnvelope
    )
    async def list_clarifications(
        project_id: UUID,
        gap_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ClarificationService, Depends(_service)],
    ) -> ClarificationHistoryEnvelope:
        try:
            rows = await service.list_clarifications(
                context, project_id=project_id, gap_id=gap_id
            )
        except ClarificationNotFound:
            raise ResourceNotFoundError from None
        except ClarificationPermissionDenied:
            raise MembershipRequiredError from None
        return ClarificationHistoryEnvelope(
            data=[
                ClarificationHistoryResponse(
                    **_question_response(entry.question).model_dump(),
                    resolution=(
                        HistoryResolutionResponse(
                            id=entry.resolution.id,
                            resolution_type=entry.resolution.resolution_type,
                            answer_text=entry.resolution.answer_text,
                            author_type=entry.resolution.author_type,
                            created_at=entry.resolution.created_at,
                        )
                        if entry.resolution is not None
                        else None
                    ),
                )
                for entry in rows
            ],
            meta=CollectionMeta(
                request_id=_request_id(), next_cursor=None, has_more=False
            ),
        )

    @router.post(
        "/{gap_id}/clarifications",
        response_model=ClarificationEnvelope,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_question(
        project_id: UUID,
        gap_id: UUID,
        body: CreateQuestionRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ClarificationService, Depends(_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ClarificationEnvelope:
        try:
            value = await service.create_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                command=CreateClarificationQuestionCommand(
                    question_text=body.question_text,
                    idempotency_key=idempotency_key,
                ),
            )
        except ClarificationNotFound:
            raise ResourceNotFoundError from None
        except ClarificationPermissionDenied:
            raise MembershipRequiredError from None
        except ClarificationInvalidState:
            raise InvalidClarificationStateError from None
        except ClarificationDuplicate:
            raise DuplicateClarificationError from None
        except ClarificationIdempotencyConflict:
            raise IdempotencyConflictError from None
        except (ClarificationValidationError, ValueError):
            raise ValidationFailedError from None
        return ClarificationEnvelope(data=_question_response(value), meta=_meta())

    @router.patch(
        "/{gap_id}/clarifications/{clarification_id}",
        response_model=ClarificationEnvelope,
    )
    async def edit_question(
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        body: EditQuestionRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ClarificationService, Depends(_service)],
    ) -> ClarificationEnvelope:
        try:
            value = await service.edit_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                clarification_id=clarification_id,
                command=EditClarificationQuestionCommand(
                    question_text=body.question_text,
                    expected_updated_at=body.expected_updated_at,
                ),
            )
        except ClarificationNotFound:
            raise ResourceNotFoundError from None
        except ClarificationPermissionDenied:
            raise MembershipRequiredError from None
        except ClarificationInvalidState:
            raise InvalidClarificationStateError from None
        except ClarificationVersionConflict:
            raise VersionConflictError from None
        except ClarificationDuplicate:
            raise DuplicateClarificationError from None
        except (ClarificationValidationError, ValueError):
            raise ValidationFailedError from None
        return ClarificationEnvelope(data=_question_response(value), meta=_meta())

    @router.post(
        "/{gap_id}/clarifications/{clarification_id}/resolutions",
        response_model=ResolutionEnvelope,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_resolution(
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        body: CreateResolutionRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ClarificationService, Depends(_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ResolutionEnvelope:
        try:
            value = await service.resolve_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                clarification_id=clarification_id,
                command=ResolveClarificationCommand(
                    resolution_type=body.resolution_type,
                    answer_text=body.answer_text,
                    author_type=body.author_type,
                    idempotency_key=idempotency_key,
                ),
            )
        except ClarificationNotFound:
            raise ResourceNotFoundError from None
        except ClarificationPermissionDenied:
            raise MembershipRequiredError from None
        except ClarificationInvalidState:
            raise InvalidClarificationStateError from None
        except ClarificationVersionConflict:
            raise VersionConflictError from None
        except ClarificationIdempotencyConflict:
            raise IdempotencyConflictError from None
        except (ClarificationValidationError, ValueError):
            raise ValidationFailedError from None
        return ResolutionEnvelope(data=_resolution_response(value), meta=_meta())

    @router.post("/{gap_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
    async def dismiss_gap(
        project_id: UUID,
        gap_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ClarificationService, Depends(_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> Response:
        try:
            await service.dismiss_gap(
                context,
                project_id=project_id,
                gap_id=gap_id,
                command=DismissGapCommand(idempotency_key=idempotency_key),
            )
        except ClarificationNotFound:
            raise ResourceNotFoundError from None
        except ClarificationPermissionDenied:
            raise MembershipRequiredError from None
        except ClarificationInvalidState:
            raise InvalidClarificationStateError from None
        except ClarificationVersionConflict:
            raise VersionConflictError from None
        except ClarificationIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ValueError:
            raise ValidationFailedError from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _question_response(value: Clarification) -> ClarificationResponse:
    return ClarificationResponse(
        id=value.id,
        gap_id=value.gap_id,
        question_text=value.question_text,
        status=value.status,
        created_by_type=value.created_by_type,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _resolution_response(value: ClarificationResolution) -> ResolutionResponse:
    return ResolutionResponse(
        id=value.id,
        clarification_id=value.clarification_id,
        resolution_type=value.resolution_type,
        answer_text=value.answer_text,
        author_type=value.author_type,
        created_at=value.created_at,
    )


def _meta() -> ResponseMeta:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Clarification API requires an active request context")
    return ResponseMeta(request_id=UUID(trace.request_id))


def _request_id() -> UUID:
    return _meta().request_id


def _gap_response(value: Gap) -> GapResponse:
    return GapResponse(
        id=value.id,
        context_version=value.context_version,
        gap_type=value.gap_type,
        severity=value.severity,
        status=value.status,
        explanation=value.explanation,
        suggested_resolution_type=value.suggested_resolution_type,
        created_at=value.created_at,
        updated_at=value.updated_at,
        resolved_at=value.resolved_at,
    )


def _encode_gap_cursor(value: Gap, filters: Mapping[str, object]) -> str:
    raw = json.dumps(
        {
            "created_at": value.created_at.isoformat(),
            "id": str(value.id),
            "filters": filters,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_gap_cursor(
    value: str | None, filters: Mapping[str, object]
) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if payload.get("filters") != filters:
            raise ValueError
        created_at = datetime.fromisoformat(payload["created_at"])
        gap_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, gap_id
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        raise ValidationFailedError from None
