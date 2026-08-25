from aria_observability import current_trace_context
from fastapi import Request
from fastapi.responses import JSONResponse


class AuthenticationRequiredError(Exception):
    """API signal mapped to the documented 401 envelope."""


class AuthenticationProviderUnavailableError(Exception):
    """API signal mapped to the owner-approved retryable Auth 503 envelope."""


class AccountBootstrapFailedError(Exception):
    """API signal mapped to the retryable Account Bootstrap 503 envelope."""


class MembershipRequiredError(Exception):
    """API signal for an authenticated subject without active Membership authority."""


class AccountContextRequiredError(Exception):
    """API signal for a missing or malformed Account selector."""


async def authentication_required_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, AuthenticationRequiredError):
        raise TypeError("Unexpected exception type for authentication handler")
    del request, error
    trace_context = current_trace_context()
    request_id = trace_context.request_id if trace_context is not None else None
    if request_id is None:
        raise RuntimeError("Authentication error requires an active request context")
    return JSONResponse(
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
        content={
            "error": {
                "code": "AUTH_REQUIRED",
                "message": "Authentication is required.",
                "retryable": False,
            },
            "meta": {"request_id": request_id},
        },
    )


async def authentication_provider_unavailable_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, AuthenticationProviderUnavailableError):
        raise TypeError("Unexpected exception type for Auth provider handler")
    del request, error
    trace_context = current_trace_context()
    request_id = trace_context.request_id if trace_context is not None else None
    if request_id is None:
        raise RuntimeError("Auth provider error requires an active request context")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "AUTH_PROVIDER_UNAVAILABLE",
                "message": "Authentication provider is temporarily unavailable.",
                "retryable": True,
            },
            "meta": {"request_id": request_id},
        },
    )


async def account_bootstrap_failed_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, AccountBootstrapFailedError):
        raise TypeError("Unexpected exception type for Account Bootstrap handler")
    del request, error
    trace_context = current_trace_context()
    request_id = trace_context.request_id if trace_context is not None else None
    if request_id is None:
        raise RuntimeError("Account Bootstrap error requires an active request context")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "ACCOUNT_BOOTSTRAP_FAILED",
                "message": "Account bootstrap is temporarily unavailable.",
                "retryable": True,
            },
            "meta": {"request_id": request_id},
        },
    )


async def membership_required_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, MembershipRequiredError):
        raise TypeError("Unexpected exception type for membership handler")
    del request, error
    trace_context = current_trace_context()
    request_id = trace_context.request_id if trace_context is not None else None
    if request_id is None:
        raise RuntimeError("Membership error requires an active request context")
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "MEMBERSHIP_REQUIRED",
                "message": "An active account membership is required.",
                "retryable": False,
            },
            "meta": {"request_id": request_id},
        },
    )


async def account_context_required_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    if not isinstance(error, AccountContextRequiredError):
        raise TypeError("Unexpected exception type for Account context handler")
    del request, error
    trace_context = current_trace_context()
    request_id = trace_context.request_id if trace_context is not None else None
    if request_id is None:
        raise RuntimeError("Account context error requires an active request context")
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "ACCOUNT_CONTEXT_REQUIRED",
                "message": "A valid account context is required.",
                "retryable": False,
            },
            "meta": {"request_id": request_id},
        },
    )
