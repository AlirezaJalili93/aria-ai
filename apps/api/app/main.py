from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from aria_observability import StructuredEventLogger, create_event_logger
from fastapi import FastAPI

from app.api.errors import AuthenticationRequiredError, authentication_required_handler
from app.api.middleware.observability import ObservabilityMiddleware
from app.api.routers.health import create_health_router
from app.core.config import ApiSettings, load_api_settings
from app.infrastructure.auth.supabase_jwt import (
    RejectingAccessTokenVerifier,
    SupabaseJwtVerifier,
)
from app.infrastructure.db.readiness import PostgresReadinessProbe, unavailable_database_probe
from app.infrastructure.queue.readiness import RedisQueueReadinessProbe, unavailable_queue_probe
from app.modules.identity.application.ports import AccessTokenVerifier


def create_app(
    settings: ApiSettings | None = None,
    database_probe: Callable[[], Awaitable[bool]] | None = None,
    queue_probe: Callable[[], Awaitable[bool]] | None = None,
    event_logger: StructuredEventLogger | None = None,
    access_token_verifier: AccessTokenVerifier | None = None,
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
    resolved_event_logger = event_logger or create_event_logger(
        service="aria-api",
        environment=resolved_settings.app_env,
        app_version=resolved_settings.app_version,
        release_commit_sha=resolved_settings.release_commit_sha,
        level=resolved_settings.log_level,
    )
    app.add_middleware(ObservabilityMiddleware, event_logger=resolved_event_logger)
    app.add_exception_handler(AuthenticationRequiredError, authentication_required_handler)
    app.state.access_token_verifier = access_token_verifier or _create_access_token_verifier(
        resolved_settings
    )
    app.include_router(
        create_health_router(resolved_settings, resolved_database_probe, resolved_queue_probe)
    )
    return app


def _create_access_token_verifier(settings: ApiSettings) -> AccessTokenVerifier:
    if settings.auth_provider_url and settings.auth_jwks_url and settings.auth_audience:
        return SupabaseJwtVerifier(
            jwks_url=str(settings.auth_jwks_url),
            issuer=str(settings.auth_provider_url),
            audience=settings.auth_audience,
            clock_skew_seconds=30,
        )
    return RejectingAccessTokenVerifier()
