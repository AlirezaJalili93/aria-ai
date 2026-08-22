from aria_observability import current_trace_context
from fastapi import Request
from fastapi.responses import JSONResponse


class AuthenticationRequiredError(Exception):
    """API signal mapped to the documented 401 envelope."""


class AuthenticationProviderUnavailableError(Exception):
    """API signal mapped to the owner-approved retryable Auth 503 envelope."""


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
