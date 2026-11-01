from __future__ import annotations

import asyncio
from typing import Protocol

from celery import Celery  # type: ignore[import-untyped]

from app.application.artifact_generation_runtime import (
    ARTIFACT_GENERATION_TASK_NAME,
    ArtifactGenerationMessage,
    ArtifactGenerationResult,
)


class ArtifactGenerationExecutor(Protocol):
    async def execute(self, message: ArtifactGenerationMessage) -> ArtifactGenerationResult: ...


def register_artifact_generation_task(
    celery_app: Celery, executor: ArtifactGenerationExecutor
) -> None:
    """Register only in controlled synthetic composition; hosted composition omits it."""

    @celery_app.task(
        name=ARTIFACT_GENERATION_TASK_NAME,
        bind=False,
        autoretry_for=(),
        ignore_result=True,
    )
    def generate_artifact(payload: object) -> dict[str, str | None]:
        message = ArtifactGenerationMessage.from_payload(payload)
        result = asyncio.run(executor.execute(message))
        return {"status": result.status, "error_code": None}
