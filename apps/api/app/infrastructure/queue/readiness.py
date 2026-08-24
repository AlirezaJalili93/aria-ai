import asyncio
import ssl
from contextlib import suppress
from urllib.parse import unquote, urlsplit

READINESS_TIMEOUT_SECONDS = 3.0
DEFAULT_REDIS_PORT = 6379


def _encode_command(*parts: str) -> bytes:
    encoded_parts = [part.encode("utf-8") for part in parts]
    command = [f"*{len(encoded_parts)}\r\n".encode()]
    for part in encoded_parts:
        command.extend((f"${len(part)}\r\n".encode(), part, b"\r\n"))
    return b"".join(command)


async def _execute_simple_command(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *parts: str,
) -> bytes:
    writer.write(_encode_command(*parts))
    await writer.drain()
    return await reader.readline()


class RedisQueueReadinessProbe:
    def __init__(
        self,
        queue_broker_url: str,
        timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
    ) -> None:
        parsed = urlsplit(queue_broker_url)
        if parsed.scheme not in {"redis", "rediss"} or parsed.hostname is None:
            raise ValueError("Queue readiness requires a Redis-compatible URL")

        self._host = parsed.hostname
        self._port = parsed.port or DEFAULT_REDIS_PORT
        self._username = unquote(parsed.username) if parsed.username else None
        self._password = unquote(parsed.password) if parsed.password else None
        self._database = parsed.path.removeprefix("/") or "0"
        self._ssl_context = ssl.create_default_context() if parsed.scheme == "rediss" else None
        self._timeout_seconds = timeout_seconds

    async def __call__(self) -> bool:
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(self._timeout_seconds):
                reader, writer = await asyncio.open_connection(
                    self._host,
                    self._port,
                    ssl=self._ssl_context,
                )
                if self._password is not None:
                    auth_parts = (
                        ("AUTH", self._username, self._password)
                        if self._username is not None
                        else ("AUTH", self._password)
                    )
                    if await _execute_simple_command(reader, writer, *auth_parts) != b"+OK\r\n":
                        return False
                if self._database != "0" and (
                    await _execute_simple_command(reader, writer, "SELECT", self._database)
                    != b"+OK\r\n"
                ):
                    return False
                return await _execute_simple_command(reader, writer, "PING") == b"+PONG\r\n"
        except (TimeoutError, OSError, ValueError):
            return False
        finally:
            if writer is not None:
                writer.close()
                with suppress(OSError):
                    await writer.wait_closed()


async def unavailable_queue_probe() -> bool:
    return False
