from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PUBLIC_SCOPE_PATHS = frozenset(
    {
        "/api/v1/public/scope-shares/resolve",
        "/api/v1/public/scope-shares/approve",
    }
)


class PublicShareNoStoreMiddleware:
    """Prevent every public Share resolution response from being cached."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") not in PUBLIC_SCOPE_PATHS:
            await self._app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        await self._app(scope, receive, send_no_store)
