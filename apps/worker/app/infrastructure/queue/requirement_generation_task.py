from __future__ import annotations

import asyncio

from celery import Celery  # type: ignore[import-untyped]

from app.application.requirement_generation_consumer import (
    RequirementGenerationConsumer,
    RequirementGenerationJobMessage,
)

REQUIREMENT_GENERATION_TASK_NAME = "aria.requirements.generate.v1"


def register_requirement_generation_task(
    celery_app: Celery, consumer: RequirementGenerationConsumer
) -> None:
    """Register only in a controlled test runtime; hosted composition omits this call."""

    @celery_app.task(
        name=REQUIREMENT_GENERATION_TASK_NAME,
        bind=False,
        autoretry_for=(),
        ignore_result=True,
    )
    def generate_requirements(payload: object) -> dict[str, str | None]:
        message = RequirementGenerationJobMessage.from_payload(payload)
        result = asyncio.run(consumer.execute(message))
        return {"status": result.status, "error_code": result.error_code}
