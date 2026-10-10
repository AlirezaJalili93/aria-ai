from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    IdempotencyConflictError,
    MembershipRequiredError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.sharing.application.service import (
    CreateScopeShareLinkCommand,
    RevokeScopeShareLinkCommand,
    ScopeShareLinkAccessNotFound,
    ScopeShareLinkIdempotencyConflict,
    ScopeShareLinkListItem,
    ScopeShareLinkPermissionDenied,
    ScopeShareLinkService,
)
from app.modules.sharing.domain.scope_share_link import ScopeShareLinkValidationError


class CreateScopeShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expires_at: datetime


class ScopeShareLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    scope_version_no: int
    expires_at: datetime
    token: str | None
    token_available: bool


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    replayed: bool


class ScopeShareLinkEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ScopeShareLinkResponse
    meta: ResponseMeta


class ReadResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class ScopeShareLinkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    scope_version_no: int
    status: Literal["active", "expired", "revoked"]
    expires_at: datetime
    created_at: datetime
    can_revoke: bool


class ScopeShareLinkCollectionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ScopeShareLinkListResponse]
    meta: ReadResponseMeta


class NoScopeDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: Literal["none"] = "none"
    scope_version_no: int


class ScopeApprovalDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: Literal["approval"] = "approval"
    scope_version_no: int
    approval_id: UUID
    guest_name: str
    approved_at: datetime


class ScopeChangeRequestDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: Literal["change_request"] = "change_request"
    scope_version_no: int
    change_request_id: UUID
    guest_name: str
    comment: str
    requested_at: datetime


ScopeDecisionResponse = Annotated[
    NoScopeDecisionResponse | ScopeApprovalDecisionResponse | ScopeChangeRequestDecisionResponse,
    Field(discriminator="decision_type"),
]


class ScopeDecisionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ScopeDecisionResponse
    meta: ReadResponseMeta


def _service(request: Request) -> ScopeShareLinkService:
    return cast(ScopeShareLinkService, request.app.state.scope_share_link_service)


def create_scope_shares_router() -> APIRouter:
    router = APIRouter(tags=["scope-sharing"])

    @router.post(
        "/projects/{project_id}/scope/versions/{version_no}/share",
        response_model=ScopeShareLinkEnvelope,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_scope_share(
        project_id: UUID,
        version_no: int,
        body: CreateScopeShareRequest,
        response: Response,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeShareLinkService, Depends(_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ScopeShareLinkEnvelope:
        try:
            result = await service.create(
                context,
                project_id=project_id,
                command=CreateScopeShareLinkCommand(
                    version_no=version_no,
                    expires_at=body.expires_at,
                    idempotency_key=idempotency_key,
                ),
            )
        except ScopeShareLinkAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeShareLinkPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeShareLinkIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ScopeShareLinkValidationError:
            raise ValidationFailedError from None

        if result.replayed:
            response.status_code = status.HTTP_200_OK
        return ScopeShareLinkEnvelope(
            data=ScopeShareLinkResponse(
                id=result.link.id,
                scope_version_no=version_no,
                expires_at=result.link.expires_at,
                token=result.public_token,
                token_available=result.token_available,
            ),
            meta=ResponseMeta(request_id=_request_id(), replayed=result.replayed),
        )

    @router.get(
        "/projects/{project_id}/scope/versions/{version_no}/shares",
        response_model=ScopeShareLinkCollectionEnvelope,
    )
    async def list_scope_shares(
        project_id: UUID,
        version_no: int,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeShareLinkService, Depends(_service)],
    ) -> ScopeShareLinkCollectionEnvelope:
        try:
            rows = await service.list_for_version(
                context,
                project_id=project_id,
                version_no=version_no,
            )
        except ScopeShareLinkAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeShareLinkPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeShareLinkValidationError:
            raise ValidationFailedError from None
        return ScopeShareLinkCollectionEnvelope(
            data=[_share_projection(row) for row in rows],
            meta=ReadResponseMeta(request_id=_request_id()),
        )

    @router.get(
        "/projects/{project_id}/scope/versions/{version_no}/decision",
        response_model=ScopeDecisionEnvelope,
    )
    async def get_scope_decision(
        project_id: UUID,
        version_no: int,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeShareLinkService, Depends(_service)],
    ) -> ScopeDecisionEnvelope:
        try:
            decision = await service.decision_for_version(
                context,
                project_id=project_id,
                version_no=version_no,
            )
        except ScopeShareLinkAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeShareLinkPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeShareLinkValidationError:
            raise ValidationFailedError from None
        if decision.decision_type == "approval":
            data: ScopeDecisionResponse = ScopeApprovalDecisionResponse(
                scope_version_no=decision.scope_version_no,
                approval_id=_required(decision.decision_id),
                guest_name=_required(decision.guest_name),
                approved_at=_required(decision.decided_at),
            )
        elif decision.decision_type == "change_request":
            data = ScopeChangeRequestDecisionResponse(
                scope_version_no=decision.scope_version_no,
                change_request_id=_required(decision.decision_id),
                guest_name=_required(decision.guest_name),
                comment=_required(decision.comment),
                requested_at=_required(decision.decided_at),
            )
        else:
            data = NoScopeDecisionResponse(scope_version_no=decision.scope_version_no)
        return ScopeDecisionEnvelope(data=data, meta=ReadResponseMeta(request_id=_request_id()))

    @router.post(
        "/projects/{project_id}/scope-shares/{share_link_id}/revoke",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def revoke_scope_share(
        project_id: UUID,
        share_link_id: UUID,
        request: Request,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ScopeShareLinkService, Depends(_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> Response:
        if await request.body() != b"":
            raise ValidationFailedError
        try:
            await service.revoke(
                context,
                project_id=project_id,
                share_link_id=share_link_id,
                command=RevokeScopeShareLinkCommand(idempotency_key=idempotency_key),
            )
        except ScopeShareLinkAccessNotFound:
            raise ResourceNotFoundError from None
        except ScopeShareLinkPermissionDenied:
            raise MembershipRequiredError from None
        except ScopeShareLinkIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ScopeShareLinkValidationError:
            raise ValidationFailedError from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _request_id() -> UUID:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Scope Share API requires an active request context")
    return UUID(trace.request_id)


def _share_projection(row: ScopeShareLinkListItem) -> ScopeShareLinkListResponse:
    return ScopeShareLinkListResponse(
        id=row.id,
        scope_version_no=row.scope_version_no,
        status=row.status,
        expires_at=row.expires_at,
        created_at=row.created_at,
        can_revoke=row.can_revoke,
    )


def _required[T](value: T | None) -> T:
    if value is None:
        raise RuntimeError("Scope decision projection is incomplete")
    return value
