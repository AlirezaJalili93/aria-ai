from typing import Annotated, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.authentication import require_authenticated_identity
from app.modules.identity.application.account_discovery import AccountDiscovery
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import MembershipRole


class AccountItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    role: MembershipRole


class CollectionMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    next_cursor: None = None
    has_more: bool = False


class AccountsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[AccountItem]
    meta: CollectionMeta


def _account_discovery(request: Request) -> AccountDiscovery:
    return cast(AccountDiscovery, request.app.state.account_discovery)


def create_accounts_router() -> APIRouter:
    router = APIRouter(tags=["accounts"])

    @router.get("/accounts", response_model=AccountsResponse)
    async def list_accounts(
        identity: Annotated[AuthenticatedIdentity, Depends(require_authenticated_identity)],
        discovery: Annotated[AccountDiscovery, Depends(_account_discovery)],
    ) -> AccountsResponse:
        accounts = await discovery.execute(identity)
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Account Discovery requires an active request context")
        return AccountsResponse(
            data=[AccountItem(id=item.id, role=item.role) for item in accounts],
            meta=CollectionMeta(request_id=UUID(trace.request_id)),
        )

    return router
