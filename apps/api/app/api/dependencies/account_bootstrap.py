from time import perf_counter
from typing import Annotated, cast

from aria_observability import StructuredEventLogger
from fastapi import Depends, Request

from app.api.dependencies.authentication import require_authenticated_identity
from app.api.errors import MembershipRequiredError
from app.modules.identity.application.account_bootstrap import (
    AccountBootstrapContext,
    AccountBootstrapper,
    ActiveMembershipRequired,
    inactive_account_bootstrap_context,
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
    return await _execute_bootstrap(
        identity,
        bootstrapper,
        event_logger,
        allow_inactive=False,
    )


async def ensure_bootstrapped_identity(
    identity: Annotated[AuthenticatedIdentity, Depends(require_authenticated_identity)],
    bootstrapper: Annotated[AccountBootstrapper, Depends(_account_bootstrapper)],
    event_logger: Annotated[StructuredEventLogger, Depends(_event_logger)],
) -> AccountBootstrapContext:
    """Ensure persistence exists while deferring Account-specific authorization."""
    return await _execute_bootstrap(
        identity,
        bootstrapper,
        event_logger,
        allow_inactive=True,
    )


async def _execute_bootstrap(
    identity: AuthenticatedIdentity,
    bootstrapper: AccountBootstrapper,
    event_logger: StructuredEventLogger,
    *,
    allow_inactive: bool,
) -> AccountBootstrapContext:
    started_at = perf_counter()
    event_logger.emit("account.bootstrap_started")
    try:
        context = await bootstrapper.execute(identity)
    except ActiveMembershipRequired:
        if allow_inactive:
            context = inactive_account_bootstrap_context(identity)
            event_logger.emit(
                "account.bootstrap_resolved",
                duration_ms=(perf_counter() - started_at) * 1000,
            )
            return context
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

    event_logger.emit(
        "account.bootstrap_completed" if context.created else "account.bootstrap_resolved",
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return context
