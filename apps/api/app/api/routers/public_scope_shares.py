from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.api.errors import (
    IdempotencyConflictError,
    ResourceNotFoundError,
    ScopeAlreadyApprovedError,
    ScopeChangesAlreadyRequestedError,
    ValidationFailedError,
)
from app.modules.scope.domain.scope_version import ScopeVersionStatus
from app.modules.sharing.application.public_approval import (
    ApprovePublicScopeCommand,
    PublicScopeAlreadyApproved,
    PublicScopeApprovalIdempotencyConflict,
    PublicScopeApprovalNotFound,
    PublicScopeApprovalService,
)
from app.modules.sharing.application.public_change_request import (
    PublicScopeChangeRequestIdempotencyConflict,
    PublicScopeChangeRequestNotFound,
    PublicScopeChangeRequestService,
    RequestPublicScopeChangesCommand,
)
from app.modules.sharing.application.public_decision_errors import (
    PublicScopeChangesAlreadyRequested,
)
from app.modules.sharing.application.public_resolver import (
    PublicScopeShareNotFound,
    PublicScopeShareResolver,
)


class ResolvePublicScopeShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class PublicScopeSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_no: int
    decision_status: ScopeVersionStatus
    snapshot_data: dict[str, object]


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class PublicScopeSnapshotEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PublicScopeSnapshotResponse
    meta: ResponseMeta


class ApprovePublicScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    guest_name: str
    explicit_consent: StrictBool = Field()

    @model_validator(mode="after")
    def consent_must_be_true(self) -> ApprovePublicScopeRequest:
        if self.explicit_consent is not True:
            raise ValueError("explicit_consent must be true")
        return self


class PublicScopeApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    scope_version_no: int
    status: Literal["approved"] = "approved"
    guest_name: str
    approved_at: datetime


class ApprovalResponseMeta(ResponseMeta):
    replayed: bool


class PublicScopeApprovalEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PublicScopeApprovalResponse
    meta: ApprovalResponseMeta


class RequestPublicScopeChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    guest_name: str
    comment: str


class PublicScopeChangeRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_request_id: UUID
    scope_version_no: int
    status: Literal["changes_requested"] = "changes_requested"
    guest_name: str
    requested_at: datetime


class PublicScopeChangeRequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PublicScopeChangeRequestResponse
    meta: ApprovalResponseMeta


def _resolver(request: Request) -> PublicScopeShareResolver:
    return cast(PublicScopeShareResolver, request.app.state.public_scope_share_resolver)


def _approval_service(request: Request) -> PublicScopeApprovalService:
    return cast(PublicScopeApprovalService, request.app.state.public_scope_approval_service)


def _change_request_service(request: Request) -> PublicScopeChangeRequestService:
    return cast(
        PublicScopeChangeRequestService,
        request.app.state.public_scope_change_request_service,
    )


def create_public_scope_shares_router() -> APIRouter:
    router = APIRouter(prefix="/public/scope-shares", tags=["public-scope-sharing"])

    @router.post("/resolve", response_model=PublicScopeSnapshotEnvelope)
    async def resolve_public_scope_share(
        body: ResolvePublicScopeShareRequest,
        resolver: Annotated[PublicScopeShareResolver, Depends(_resolver)],
    ) -> PublicScopeSnapshotEnvelope:
        try:
            resolved = await resolver.resolve(token=body.token)
        except PublicScopeShareNotFound:
            raise ResourceNotFoundError from None
        return PublicScopeSnapshotEnvelope(
            data=PublicScopeSnapshotResponse(
                version_no=resolved.version_no,
                decision_status=resolved.decision_status,
                snapshot_data=resolved.snapshot_data,
            ),
            meta=ResponseMeta(request_id=_request_id()),
        )

    @router.post(
        "/approve",
        response_model=PublicScopeApprovalEnvelope,
        status_code=status.HTTP_201_CREATED,
    )
    async def approve_public_scope_share(
        body: ApprovePublicScopeRequest,
        response: Response,
        service: Annotated[PublicScopeApprovalService, Depends(_approval_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> PublicScopeApprovalEnvelope:
        try:
            result = await service.approve(
                ApprovePublicScopeCommand(
                    token=body.token,
                    guest_name=body.guest_name,
                    explicit_consent=body.explicit_consent,
                    idempotency_key=idempotency_key,
                )
            )
        except PublicScopeApprovalNotFound:
            raise ResourceNotFoundError from None
        except PublicScopeApprovalIdempotencyConflict:
            raise IdempotencyConflictError from None
        except PublicScopeAlreadyApproved:
            raise ScopeAlreadyApprovedError from None
        except PublicScopeChangesAlreadyRequested:
            raise ScopeChangesAlreadyRequestedError from None
        except ValueError:
            raise ValidationFailedError from None

        if result.replayed:
            response.status_code = status.HTTP_200_OK
        approval = result.approval
        return PublicScopeApprovalEnvelope(
            data=PublicScopeApprovalResponse(
                approval_id=approval.id,
                scope_version_no=approval.version_no,
                guest_name=approval.guest_name,
                approved_at=approval.approved_at,
            ),
            meta=ApprovalResponseMeta(request_id=_request_id(), replayed=result.replayed),
        )

    @router.post(
        "/request-changes",
        response_model=PublicScopeChangeRequestEnvelope,
        status_code=status.HTTP_201_CREATED,
    )
    async def request_public_scope_changes(
        body: RequestPublicScopeChangesRequest,
        response: Response,
        service: Annotated[PublicScopeChangeRequestService, Depends(_change_request_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> PublicScopeChangeRequestEnvelope:
        try:
            result = await service.request_changes(
                RequestPublicScopeChangesCommand(
                    token=body.token,
                    guest_name=body.guest_name,
                    comment=body.comment,
                    idempotency_key=idempotency_key,
                )
            )
        except PublicScopeChangeRequestNotFound:
            raise ResourceNotFoundError from None
        except PublicScopeChangeRequestIdempotencyConflict:
            raise IdempotencyConflictError from None
        except PublicScopeAlreadyApproved:
            raise ScopeAlreadyApprovedError from None
        except PublicScopeChangesAlreadyRequested:
            raise ScopeChangesAlreadyRequestedError from None
        except ValueError:
            raise ValidationFailedError from None

        if result.replayed:
            response.status_code = status.HTTP_200_OK
        change_request = result.change_request
        return PublicScopeChangeRequestEnvelope(
            data=PublicScopeChangeRequestResponse(
                change_request_id=change_request.id,
                scope_version_no=change_request.version_no,
                guest_name=change_request.guest_name,
                requested_at=change_request.requested_at,
            ),
            meta=ApprovalResponseMeta(request_id=_request_id(), replayed=result.replayed),
        )

    return router


def _request_id() -> UUID:
    trace = current_trace_context()
    if trace is None or trace.request_id is None:
        raise RuntimeError("Public Scope Share API requires an active request context")
    return UUID(trace.request_id)
