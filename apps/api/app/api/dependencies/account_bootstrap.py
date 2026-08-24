from time import perf_counter
from typing import Annotated, cast

from aria_observability import StructuredEventLogger, enrich_trace_context
from fastapi import Depends, Request

from app.api.dependencies.authentication import require_authenticated_identity
from app.api.errors import MembershipRequiredError
from app.modules.identity.application.account_bootstrap import (
    AccountBootstrapContext,
    AccountBootstrapper,
    ActiveMembershipRequired,
)
from app.modules.identity.application.ports import AuthenticatedIdentity


def _account_bootstrapper(request: Request) -> AccountBootstrapper:
    return cast(AccountBootstrapper, request.app.state.account_bootstrapper)


def _event_logger(request: Request) -> StructuredEventLogger:
    return cast(StructuredEventLogger, request.app.state.event_logger)


async def require_bootstrapped_identity(
    identity: Annotated[AuthenticatedIdentity, Depends(require_authenticated_identity)],
    bootstrapper: Annotated[AccountBootstrapper, Depends(_account_bootstrapper)],
    event_logger: Annotated[StructuredEventLogger, Depends(_event_logger)],
) -> AccountBootstrapContext:
    started_at = perf_counter()
    event_logger.emit("account.bootstrap_started")
    try:
        context = await bootstrapper.execute(identity)
    except ActiveMembershipRequired:
        event_logger.emit(
            "account.bootstrap_failed",
            level="WARNING",
            duration_ms=(perf_counter() - started_at) * 1000,
            error_code="MEMBERSHIP_REQUIRED",
            reason_code="active_membership_required",
        )
        raise MembershipRequiredError from None
    except Exception:
        event_logger.emit(
            "account.bootstrap_failed",
            level="ERROR",
            duration_ms=(perf_counter() - started_at) * 1000,
            error_code="ACCOUNT_BOOTSTRAP_FAILED",
            reason_code="bootstrap_failed",
        )
        raise

    if len(context.active_memberships) == 1:
        enrich_trace_context(account_id=str(context.active_memberships[0].account_id))
    event_logger.emit(
        "account.bootstrap_completed" if context.created else "account.bootstrap_resolved",
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return context
