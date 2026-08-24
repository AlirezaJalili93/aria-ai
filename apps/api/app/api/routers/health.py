import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict

from app.core.config import ApiSettings

DatabaseProbe = Callable[[], Awaitable[bool]]


class ServiceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: Literal["aria-api"] = "aria-api"
    environment: Literal["local", "test", "staging", "production"]
    version: str
    release_commit_sha: str | None


class DependencyChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration: Literal["pass"] = "pass"
    database: Literal["pass", "fail"]
    queue: Literal["pass", "fail"]


class ReadinessResponse(ServiceMetadata):
    status: Literal["ready", "not_ready"]
    checks: DependencyChecks


class LivenessResponse(ServiceMetadata):
    status: Literal["alive"]


def create_health_router(
    settings: ApiSettings,
    database_probe: DatabaseProbe,
    queue_probe: DatabaseProbe,
) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live", response_model=LivenessResponse)
    async def get_liveness() -> LivenessResponse:
        return LivenessResponse(
            status="alive",
            environment=settings.app_env,
            version=settings.app_version,
            release_commit_sha=settings.release_commit_sha,
        )

    @router.get(
        "/ready",
        response_model=ReadinessResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    )
    async def get_readiness(response: Response) -> ReadinessResponse:
        results = await asyncio.gather(database_probe(), queue_probe(), return_exceptions=True)
        database_ready = results[0] is True
        queue_ready = results[1] is True
        if not database_ready or not queue_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ReadinessResponse(
                status="not_ready",
                environment=settings.app_env,
                version=settings.app_version,
                release_commit_sha=settings.release_commit_sha,
                checks=DependencyChecks(
                    database="pass" if database_ready else "fail",
                    queue="pass" if queue_ready else "fail",
                ),
            )

        return ReadinessResponse(
            status="ready",
            environment=settings.app_env,
            version=settings.app_version,
            release_commit_sha=settings.release_commit_sha,
            checks=DependencyChecks(database="pass", queue="pass"),
        )

    return router
