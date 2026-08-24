from time import perf_counter
from typing import Annotated, cast

from aria_observability import StructuredEventLogger
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.errors import AuthenticationProviderUnavailableError, AuthenticationRequiredError
from app.modules.identity.application.ports import (
    AccessTokenVerifier,
    AuthenticatedIdentity,
    AuthProviderUnavailable,
    InvalidAccessToken,
)

_bearer_scheme = HTTPBearer(auto_error=False)


def _access_token_verifier(request: Request) -> AccessTokenVerifier:
    return cast(AccessTokenVerifier, request.app.state.access_token_verifier)


def _event_logger(request: Request) -> StructuredEventLogger:
    return cast(StructuredEventLogger, request.app.state.event_logger)


async def require_authenticated_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    verifier: Annotated[AccessTokenVerifier, Depends(_access_token_verifier)],
) -> AuthenticatedIdentity:
    started_at = perf_counter()
    event_logger = _event_logger(request)
    if credentials is None or credentials.scheme.lower() != "bearer":
        event_logger.emit(
            "auth.verification_rejected",
            provider=verifier.provider_name,
            reason_code="missing_credential",
            duration_ms=(perf_counter() - started_at) * 1000,
            error_code="AUTH_REQUIRED",
        )
        raise AuthenticationRequiredError
    try:
        identity = await verifier.verify(credentials.credentials)
    except InvalidAccessToken as error:
        event_logger.emit(
            "auth.verification_rejected",
            provider=verifier.provider_name,
            reason_code=error.reason_code,
            duration_ms=(perf_counter() - started_at) * 1000,
            error_code="AUTH_REQUIRED",
        )
        raise AuthenticationRequiredError from None
    except AuthProviderUnavailable as error:
        event_logger.emit(
            "auth.provider_unavailable",
            level="ERROR",
            provider=verifier.provider_name,
            reason_code=error.reason_code,
            duration_ms=(perf_counter() - started_at) * 1000,
            error_code="AUTH_PROVIDER_UNAVAILABLE",
        )
        raise AuthenticationProviderUnavailableError from None

    event_logger.emit(
        "auth.verification_succeeded",
        provider=verifier.provider_name,
        duration_ms=(perf_counter() - started_at) * 1000,
    )
    return identity
