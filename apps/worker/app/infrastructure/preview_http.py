"""Explicit loopback-only synthetic proof adapter; never a production HTTP server.

No automatic bootstrap, directory serving, proxy, cookie/session or diagnostics sink.
Python's standard HTTP parser defaults are inherited only for this disposable proof.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from app.application.preview_access import PreviewAccessService, PreviewReadResult


@dataclass(frozen=True, slots=True)
class PreviewHttpListener:
    port: int


def _denied() -> PreviewReadResult:
    return PreviewReadResult(
        404,
        {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        b"",
        "RESOURCE_NOT_FOUND",
    )


@asynccontextmanager
async def controlled_preview_listener(
    service_factory: Callable[[int], PreviewAccessService],
) -> AsyncIterator[PreviewHttpListener]:
    """Bind only an ephemeral loopback socket; service supplies frozen synthetic guards."""
    loop = asyncio.get_running_loop()

    class Server(ThreadingHTTPServer):
        # Join active handlers while their Application loop is still running on cleanup.
        daemon_threads = False

        def handle_error(self, request: object, client_address: object) -> None:
            # BaseServer's default traceback can contain raw requests/credentials. Never emit it.
            pass

    class Handler(BaseHTTPRequestHandler):
        raw_requestline: bytes
        _raw_target: str

        def parse_request(self) -> bool:
            # BaseHTTPRequestHandler normalizes a leading // in self.path. Preserve exact
            # origin-form bytes BEFORE that parser; access validation never uses self.path.
            parts = self.raw_requestline.rstrip(b"\r\n").split(b" ")
            self._raw_target = ""
            if len(parts) != 3:
                self.request_version = "HTTP/1.0"
                self.command = ""
                self.send_error(404)
                return False
            try:
                self._raw_target = parts[1].decode("ascii")
            except UnicodeDecodeError:
                self.request_version = "HTTP/1.0"
                self.command = ""
                self.send_error(404)
                return False
            return super().parse_request()

        def send_error(
            self, code: int, message: str | None = None, explain: str | None = None
        ) -> None:
            # No parser text, request target, caller method, HTML error page or traceback.
            self.request_version = "HTTP/1.0"
            self._send(_denied())

        def log_message(self, format: str, *args: object) -> None:
            # Suppress request/error logs at their source, not after formatting a bearer URL.
            pass

        def __getattr__(self, name: str) -> Callable[[], None]:
            if name.startswith("do_"):
                return self._serve
            raise AttributeError("Unavailable controlled HTTP attribute")

        def _serve(self) -> None:
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1:
                self._send(_denied())
                return
            try:
                result = asyncio.run_coroutine_threadsafe(
                    service.read(host=hosts[0], raw_target=self._raw_target, method=self.command),
                    loop,
                ).result()
            except Exception:
                result = _denied()
            self._send(result)

        def _send(self, result: PreviewReadResult) -> None:
            self.close_connection = True
            self.send_response_only(result.status)
            for key, value in result.headers.items():
                self.send_header(key, value)
            if "Content-Length" not in result.headers:
                self.send_header("Content-Length", str(len(result.body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(result.body)

    server = Server(("127.0.0.1", 0), Handler)
    thread: Thread | None = None
    try:
        port = int(server.server_address[1])
        service = service_factory(port)
        thread = Thread(target=server.serve_forever, name="controlled-preview-http")
        thread.start()
        yield PreviewHttpListener(port)
    finally:
        if thread is not None:
            await asyncio.to_thread(server.shutdown)
        await asyncio.to_thread(server.server_close)
        if thread is not None:
            await asyncio.to_thread(thread.join)
