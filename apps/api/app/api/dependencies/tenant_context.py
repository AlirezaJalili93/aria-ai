from __future__ import annotations

from time import perf_counter
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from aria_observability import StructuredEventLogger, enrich_trace_context
from fastapi import Depends, Request

from app.api.dependencies.authentication import require_authenticated_identity
from app.api.errors import AccountContextRequiredError, MembershipRequiredError
from app.modules.identity.application.membership_resolution import ActiveMembershipRequired
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.application.tenant_context import TenantContext, TenantContextResolver


def _tenant_context_resolver(request: Request) -> TenantContextResolver:
    return cast(TenantContextResolver, request.app.state.tenant_context_resolver)


def _event_logger(request: Request) -> StructuredEventLogger:
    return cast(StructuredEventLogger, request.app.state.event_logger)


async def require_tenant_context(
    request: Request,
    identity: Annotated[AuthenticatedIdentity, Depends(require_authenticated_identity)],
    tenant_context_resolver: Annotated[
        TenantContextResolver,
        Depends(_tenant_context_resolver),
    ],
    event_logger: Annotated[StructuredEventLogger, Depends(_event_logger)],
) -> TenantContext:
    started_at = perf_counter()
    raw_account_id = request.headers.get("X-Account-ID")
    if raw_account_id is None:
        _reject_account_context(event_logger, started_at, reason_code="missing")
    if raw_account_id == "":
        _reject_account_context(event_logger, started_at, reason_code="empty")
    try:
        account_id = UUID(raw_account_id)
    except (TypeError, ValueError, AttributeError):
        _reject_account_context(event_logger, started_at, reason_code="invalid_uuid")

    try:
        tenant_context = await tenant_context_resolver.execute(identity, account_id)
    except ActiveMembershipRequired as error:
        event_logger.emit(
            "tenant.membership_denied",
            level="WARNING",
            duration_ms=(perf_counter() - started_at) * 1000,
            error_code="MEMBERSHIP_REQUIRED",
            reason_code=error.reason_code,
        )
        raise MembershipRequiredError from None

    enrich_trace_context(account_id=str(tenant_context.account_id))
    return tenant_context


def _reject_account_context(
    event_logger: StructuredEventLogger,
    started_at: float,
    *,
    reason_code: Literal["missing", "empty", "invalid_uuid"],
) -> NoReturn:
    event_logger.emit(
        "tenant.context_rejected",
        level="WARNING",
        duration_ms=(perf_counter() - started_at) * 1000,
        error_code="ACCOUNT_CONTEXT_REQUIRED",
        reason_code=reason_code,
    )
    raise AccountContextRequiredError
