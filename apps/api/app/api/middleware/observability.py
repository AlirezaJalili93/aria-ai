from time import perf_counter

from aria_observability import (
    StructuredEventLogger,
    bind_trace_context,
    resolve_http_trace_context,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, event_logger: StructuredEventLogger) -> None:
        super().__init__(app)
        self._event_logger = event_logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_context = resolve_http_trace_context(
            request.headers.get("X-Request-ID"),
            request.headers.get("X-Correlation-ID"),
        )
        started_at = perf_counter()
        with bind_trace_context(trace_context):
            try:
                response = await call_next(request)
            except Exception:
                self._event_logger.emit(
                    "http.request_failed",
                    level="ERROR",
                    route=_route_template(request),
                    duration_ms=(perf_counter() - started_at) * 1000,
                    status=500,
                    error_code="UNHANDLED_EXCEPTION",
                )
                raise

            response.headers["X-Request-ID"] = trace_context.request_id or ""
            response.headers["X-Correlation-ID"] = trace_context.correlation_id
            self._event_logger.emit(
                "http.request_completed",
                route=_route_template(request),
                duration_ms=(perf_counter() - started_at) * 1000,
                status=response.status_code,
            )
            return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if isinstance(route_path, str) else "/<unmatched>"
