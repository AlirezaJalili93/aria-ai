from aria_observability import current_trace_context
from fastapi import Request
from fastapi.exceptions import RequestValidationError
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


class ResourceNotFoundError(Exception):
    """API signal for a tenant-safe missing resource response."""


class IdempotencyConflictError(Exception):
    """API signal for an idempotency key reused with different input."""


class VersionConflictError(Exception):
    """API signal for an optimistic concurrency mismatch."""


class ForbiddenError(Exception):
    """API signal for an authenticated caller lacking role authority."""


class ValidationFailedError(Exception):
    """API signal for documented domain or cursor validation failure."""


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


async def resource_not_found_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ResourceNotFoundError):
        raise TypeError("Unexpected exception type for resource handler")
    del request, error
    return _error_response(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="The requested resource was not found.",
        retryable=False,
    )


async def idempotency_conflict_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, IdempotencyConflictError):
        raise TypeError("Unexpected exception type for idempotency handler")
    del request, error
    return _error_response(
        status_code=409,
        code="IDEMPOTENCY_CONFLICT",
        message="The idempotency key was already used with different input.",
        retryable=False,
    )


async def version_conflict_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, VersionConflictError):
        raise TypeError("Unexpected exception type for version handler")
    del request, error
    return _error_response(
        status_code=409,
        code="VERSION_CONFLICT",
        message="The resource has changed since it was read.",
        retryable=False,
    )


async def forbidden_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ForbiddenError):
        raise TypeError("Unexpected exception type for forbidden handler")
    del request, error
    return _error_response(
        status_code=403,
        code="FORBIDDEN",
        message="You do not have permission to perform this action.",
        retryable=False,
    )


async def validation_failed_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ValidationFailedError):
        raise TypeError("Unexpected exception type for validation handler")
    del request, error
    return _error_response(
        status_code=422,
        code="VALIDATION_FAILED",
        message="The request failed validation.",
        retryable=False,
    )


async def request_validation_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise TypeError("Unexpected exception type for request validation handler")
    del request, error
    return _error_response(
        status_code=422,
        code="VALIDATION_FAILED",
        message="The request failed validation.",
        retryable=False,
    )


def _error_response(
    *, status_code: int, code: str, message: str, retryable: bool
) -> JSONResponse:
    trace_context = current_trace_context()
    request_id = trace_context.request_id if trace_context is not None else None
    if request_id is None:
        raise RuntimeError("API error requires an active request context")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "retryable": retryable},
            "meta": {"request_id": request_id},
        },
    )
