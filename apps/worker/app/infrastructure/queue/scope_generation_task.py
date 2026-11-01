from __future__ import annotations

import asyncio

from celery import Celery  # type: ignore[import-untyped]

from app.application.scope_generation_consumer import (
    ScopeGenerationConsumer,
    ScopeGenerationJobMessage,
)

SCOPE_GENERATION_TASK_NAME = "aria.scope.generate.v1"


def register_scope_generation_task(celery_app: Celery, consumer: ScopeGenerationConsumer) -> None:
    """Register only in controlled tests; hosted composition omits this call."""

    @celery_app.task(
        name=SCOPE_GENERATION_TASK_NAME,
        bind=False,
        autoretry_for=(),
        ignore_result=True,
    )
    def generate_scope(payload: object) -> dict[str, str | None]:
        message = ScopeGenerationJobMessage.from_payload(payload)
        result = asyncio.run(consumer.execute(message))
        return {"status": result.status, "error_code": result.error_code}
