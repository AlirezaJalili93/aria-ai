import asyncio

from app.infrastructure.queue.readiness import RedisQueueReadinessProbe


async def _probe_local_redis_protocol() -> bool:
    async def handle_ping(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        request = await reader.readuntil(b"PING\r\n")
        writer.write(b"+PONG\r\n" if request == b"*1\r\n$4\r\nPING\r\n" else b"-ERR\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_ping, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        return await RedisQueueReadinessProbe(f"redis://127.0.0.1:{port}/0")()
    finally:
        server.close()
        await server.wait_closed()


def test_queue_readiness_performs_real_redis_compatible_ping() -> None:
    assert asyncio.run(_probe_local_redis_protocol()) is True
