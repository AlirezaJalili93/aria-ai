from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    CriticalGapsOpenError,
    IdempotencyConflictError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ScopeRevisionRequiredError,
    ScopeRevisionStaleError,
    ScopeVersionUnchangedError,
    ValidationFailedError,
    VersionConflictError,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_revision_service import (
    CreateScopeRevisionCommand,
    ScopeRevisionAccessNotFound,
    ScopeRevisionIdempotencyConflict,
    ScopeRevisionNotReady,
    ScopeRevisionPermissionDenied,
    ScopeRevisionService,
    ScopeRevisionStale,
    ScopeRevisionUnchanged,
    ScopeRevisionVersionConflict,
)
from app.modules.scope.application.scope_version_service import (
    CreateScopeVersionCommand,
    ScopeRevisionRequired,
    ScopeVersionAccessNotFound,
    ScopeVersionCreateConflict,
    ScopeVersionIdempotencyConflict,
    ScopeVersionNotReady,
    ScopeVersionPermissionDenied,
    ScopeVersionService,
    ScopeVersionUnchanged,
)
from app.modules.scope.domain.scope_version import ScopeVersion, ScopeVersionValidationError

ScopeVersionStatus = Literal["awaiting_approval", "approved", "changes_requested", "superseded"]


class CreateScopeVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_draft_updated_at: datetime


class CreateScopeRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_request_id: UUID
    expected_draft_updated_at: datetime


class ScopeVersionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_no: int
    context_version: int
    status: ScopeVersionStatus
    snapshot_hash: str
    schema_version: str
    created_at: datetime


class ScopeVersionDetailResponse(ScopeVersionSummaryResponse):
    snapshot_data: dict[str, object]


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class RevisionResponseMeta(ResponseMeta):
    replayed: bool


class CollectionMeta(ResponseMeta):
    next_cursor: str | None
    has_more: bool


class ScopeVersionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ScopeVersionSummaryResponse
    meta: ResponseMeta


class ScopeRevisionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ScopeVersionSummaryResponse
    meta: RevisionResponseMeta


class ScopeVersionDetailEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ScopeVersionDetailResponse
    meta: ResponseMeta


class ScopeVersionCollectionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ScopeVersionSummaryResponse]
    meta: CollectionMeta


def _service(request: Request) -> ScopeVersionService:
    return cast(ScopeVersionService, request.app.state.scope_version_service)


def _revision_service(request: Request) -> ScopeRevisionService:
    return cast(ScopeRevisionService, request.app.state.scope_revision_service)


def create_scope_versions_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/scope/versions", tags=["scope"])

    @router.post("", response_model=ScopeVersionEnvelope, status_code=status.HTTP_201_CREATED)
    async def create_scope_version(
        project_id: UUID,
        body: CreateScopeVersionRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeVersionService, Depends(_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ScopeVersionEnvelope:
        try:
            version = await service.create(
                context,
                project_id=project_id,
                command=CreateScopeVersionCommand(
                    expected_draft_updated_at=body.expected_draft_updated_at,
                    idempotency_key=idempotency_key,
                ),
            )
        except ScopeVersionAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeVersionPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeVersionCreateConflict:
            raise VersionConflictError from None
        except ScopeVersionNotReady:
            raise CriticalGapsOpenError from None
        except ScopeVersionUnchanged:
            raise ScopeVersionUnchangedError from None
        except ScopeRevisionRequired:
            raise ScopeRevisionRequiredError from None
        except ScopeVersionIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ScopeVersionValidationError:
            raise ValidationFailedError from None
        return ScopeVersionEnvelope(
            data=_summary(version), meta=ResponseMeta(request_id=_request_id())
        )

    @router.post(
        "/{version_no}/revisions",
        response_model=ScopeRevisionEnvelope,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_scope_revision(
        project_id: UUID,
        version_no: int,
        body: CreateScopeRevisionRequest,
        response: Response,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeRevisionService, Depends(_revision_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ScopeRevisionEnvelope:
        try:
            result = await service.create(
                context,
                project_id=project_id,
                target_version_no=version_no,
                command=CreateScopeRevisionCommand(
                    change_request_id=body.change_request_id,
                    expected_draft_updated_at=body.expected_draft_updated_at,
                    idempotency_key=idempotency_key,
                ),
            )
        except ScopeRevisionAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeRevisionPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeRevisionIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ScopeRevisionStale:
            raise ScopeRevisionStaleError from None
        except ScopeRevisionVersionConflict:
            raise VersionConflictError from None
        except ScopeRevisionNotReady:
            raise CriticalGapsOpenError from None
        except ScopeRevisionUnchanged:
            raise ScopeVersionUnchangedError from None
        except ScopeVersionValidationError:
            raise ValidationFailedError from None
        if result.replayed:
            response.status_code = status.HTTP_200_OK
        return ScopeRevisionEnvelope(
            data=_summary(result.version),
            meta=RevisionResponseMeta(request_id=_request_id(), replayed=result.replayed),
        )

    @router.get("", response_model=ScopeVersionCollectionEnvelope)
    async def list_scope_versions(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeVersionService, Depends(_service)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> ScopeVersionCollectionEnvelope:
        before_version_no = _decode_cursor(cursor)
        try:
            rows = await service.list(
                context,
                project_id=project_id,
                limit=limit + 1,
                before_version_no=before_version_no,
            )
        except ScopeVersionAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeVersionPermissionDenied:
            raise MembershipRequiredError from None
        has_more = len(rows) > limit
        page = rows[:limit]
        return ScopeVersionCollectionEnvelope(
            data=[_summary(version) for version in page],
            meta=CollectionMeta(
                request_id=_request_id(),
                next_cursor=_encode_cursor(page[-1].version_no) if has_more and page else None,
                has_more=has_more,
            ),
        )

    @router.get("/{version_no}", response_model=ScopeVersionDetailEnvelope)
    async def get_scope_version(
        project_id: UUID,
        version_no: int,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeVersionService, Depends(_service)],
    ) -> ScopeVersionDetailEnvelope:
        if version_no < 1:
            raise ValidationFailedError
        try:
            version = await service.get(context, project_id=project_id, version_no=version_no)
        except ScopeVersionAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeVersionPermissionDenied:
            raise MembershipRequiredError from None
        return ScopeVersionDetailEnvelope(
            data=ScopeVersionDetailResponse(
                **_summary(version).model_dump(), snapshot_data=version.snapshot_data
            ),
            meta=ResponseMeta(request_id=_request_id()),
        )

    return router


def _summary(version: ScopeVersion) -> ScopeVersionSummaryResponse:
    return ScopeVersionSummaryResponse(
        version_no=version.version_no,
        context_version=version.context_version,
        status=version.status,
        snapshot_hash=version.snapshot_hash,
        schema_version=str(version.snapshot_data["schema_version"]),
        created_at=version.created_at,
    )


def _request_id() -> UUID:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Scope Version API requires an active request context")
    return UUID(trace.request_id)


def _encode_cursor(version_no: int) -> str:
    raw = json.dumps({"before_version_no": version_no}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        version_no = int(payload["before_version_no"])
        if version_no < 1:
            raise ValueError
        return version_no
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ValidationFailedError from None
