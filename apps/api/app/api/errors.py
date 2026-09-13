from contextlib import suppress

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


class ScopeDraftStaleError(Exception):
    """API signal for mutation of a historical Scope Draft."""


class CriticalGapsOpenError(Exception):
    """API signal for a Scope freeze blocked by unresolved Critical Gaps."""


class ScopeVersionUnchangedError(Exception):
    """API signal for a Scope freeze identical to the latest snapshot."""


class InvalidContextItemStateError(Exception):
    """API signal for a Context Item command rejected by its immutable state."""


class InvalidRequirementStateError(Exception):
    """API signal for a Requirement command rejected by its lifecycle state."""


class InvalidClarificationStateError(Exception):
    """API signal for a Clarification or Gap command rejected by terminal state."""


class DuplicateClarificationError(Exception):
    """API signal for an exact duplicate open Clarification question."""


class ContextVersionRequiredError(Exception):
    """API signal for a manual Requirement without a valid Project Context Version."""


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
    del error
    route = request.scope.get("route")
    route_template = getattr(route, "path", None)
    resource_type = _resource_type_for_route(route_template)
    project_id = request.path_params.get("project_id")
    with suppress(Exception):
        request.app.state.event_logger.emit(
            "resource.access_denied",
            level="WARNING",
            route=route_template if isinstance(route_template, str) else "/<unmatched>",
            project_id=str(project_id) if project_id is not None else None,
            resource_type=resource_type,
            operation=request.method.lower(),
            reason_code="not_visible_in_tenant_scope",
            error_code="RESOURCE_NOT_FOUND",
        )
    return _error_response(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="The requested resource was not found.",
        retryable=False,
    )


def _resource_type_for_route(route_template: object) -> str:
    if not isinstance(route_template, str):
        return "resource"
    if "/scope/versions" in route_template:
        return "scope_version"
    if "/scope/draft" in route_template:
        return "scope_draft"
    if "/context-items" in route_template:
        return "context_item"
    if "/context-sources" in route_template:
        return "context_source"
    if "/requirements" in route_template:
        return "requirement"
    if "/gaps" in route_template:
        return "gap"
    if "/jobs" in route_template:
        return "job"
    if "/projects" in route_template:
        return "project"
    return "resource"


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


async def scope_draft_stale_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ScopeDraftStaleError):
        raise TypeError("Unexpected exception type for Scope Draft stale handler")
    del request, error
    return _error_response(
        status_code=409,
        code="SCOPE_DRAFT_STALE",
        message="The Scope Draft belongs to a historical Context Version.",
        retryable=False,
    )


async def critical_gaps_open_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, CriticalGapsOpenError):
        raise TypeError("Unexpected exception type for Critical Gaps handler")
    del request, error
    return _error_response(
        status_code=422,
        code="CRITICAL_GAPS_OPEN",
        message="Unresolved Critical Gaps prevent freezing the Scope.",
        retryable=False,
    )


async def scope_version_unchanged_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, ScopeVersionUnchangedError):
        raise TypeError("Unexpected exception type for unchanged Scope Version handler")
    del request, error
    return _error_response(
        status_code=409,
        code="SCOPE_VERSION_UNCHANGED",
        message="The current Scope is unchanged from the latest version.",
        retryable=False,
    )


async def invalid_context_item_state_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, InvalidContextItemStateError):
        raise TypeError("Unexpected exception type for Context Item state handler")
    del request, error
    return _error_response(
        status_code=409,
        code="INVALID_CONTEXT_ITEM_STATE",
        message="The Context Item is not mutable in its current state.",
        retryable=False,
    )


async def invalid_requirement_state_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, InvalidRequirementStateError):
        raise TypeError("Unexpected exception type for Requirement state handler")
    del request, error
    return _error_response(
        status_code=409,
        code="INVALID_REQUIREMENT_STATE",
        message="The Requirement is not mutable in its current state.",
        retryable=False,
    )


async def invalid_clarification_state_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, InvalidClarificationStateError):
        raise TypeError("Unexpected exception type for Clarification state handler")
    del request, error
    return _error_response(
        status_code=409,
        code="INVALID_CLARIFICATION_STATE",
        message="The Clarification or Gap is not mutable in its current state.",
        retryable=False,
    )


async def duplicate_clarification_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, DuplicateClarificationError):
        raise TypeError("Unexpected exception type for duplicate Clarification handler")
    del request, error
    return _error_response(
        status_code=409,
        code="DUPLICATE_CLARIFICATION",
        message="The same open Clarification already exists for this Gap.",
        retryable=False,
    )


async def context_version_required_handler(
    request: Request, error: Exception
) -> JSONResponse:
    if not isinstance(error, ContextVersionRequiredError):
        raise TypeError("Unexpected exception type for Context Version handler")
    del request, error
    return _error_response(
        status_code=422,
        code="CONTEXT_VERSION_REQUIRED",
        message="A valid Project Context Version is required.",
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
