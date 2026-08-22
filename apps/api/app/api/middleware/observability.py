from time import perf_counter

from aria_observability import (
    StructuredEventLogger,
    bind_trace_context,
    resolve_http_trace_context,
)
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ObservabilityMiddleware:
    """Pure ASGI request telemetry that preserves downstream context enrichment."""

    def __init__(self, app: ASGIApp, event_logger: StructuredEventLogger) -> None:
        self._app = app
        self._event_logger = event_logger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        trace_context = resolve_http_trace_context(
            request_headers.get("X-Request-ID"),
            request_headers.get("X-Correlation-ID"),
        )
        started_at = perf_counter()
        response_status = 500

        async def send_with_trace_headers(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = trace_context.request_id or ""
                response_headers["X-Correlation-ID"] = trace_context.correlation_id
            await send(message)

        with bind_trace_context(trace_context):
            try:
                await self._app(scope, receive, send_with_trace_headers)
            except Exception as error:
                self._event_logger.emit(
                    "http.request_failed",
                    level="ERROR",
                    route=_route_template(scope),
                    duration_ms=(perf_counter() - started_at) * 1000,
                    status=500,
                    error_code="UNHANDLED_EXCEPTION",
                    exception_type=type(error).__name__,
                    component="http.middleware",
                    operation="request",
                )
                raise

            self._event_logger.emit(
                "http.request_completed",
                route=_route_template(scope),
                duration_ms=(perf_counter() - started_at) * 1000,
                status=response_status,
            )


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if isinstance(route_path, str) else "/<unmatched>"
