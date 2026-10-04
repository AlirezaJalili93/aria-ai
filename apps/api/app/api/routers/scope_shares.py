from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict

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
