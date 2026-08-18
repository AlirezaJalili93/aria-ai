from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers.health import create_health_router
from app.core.config import ApiSettings, load_api_settings
from app.infrastructure.db.readiness import PostgresReadinessProbe, unavailable_database_probe
from app.infrastructure.queue.readiness import RedisQueueReadinessProbe, unavailable_queue_probe


def create_app(
    settings: ApiSettings | None = None,
    database_probe: Callable[[], Awaitable[bool]] | None = None,
    queue_probe: Callable[[], Awaitable[bool]] | None = None,
) -> FastAPI:
    resolved_settings = settings or load_api_settings()
    owned_database_probe = (
        PostgresReadinessProbe(resolved_settings.database_url.get_secret_value())
        if database_probe is None and resolved_settings.database_url
        else None
    )
    resolved_database_probe = database_probe or owned_database_probe or unavailable_database_probe
    resolved_queue_probe = queue_probe or (
        RedisQueueReadinessProbe(resolved_settings.queue_broker_url.get_secret_value())
        if resolved_settings.queue_broker_url
        else unavailable_queue_probe
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if owned_database_probe is not None:
            await owned_database_probe.close()

    app = FastAPI(
        title="Aria API",
        version=resolved_settings.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.include_router(
        create_health_router(resolved_settings, resolved_database_probe, resolved_queue_probe)
    )
    return app
