from __future__ import annotations

import asyncio

from celery import Celery  # type: ignore[import-untyped]

from app.application.context_structuring_consumer import (
    ContextStructuringConsumer,
    ContextStructuringJobMessage,
)

CONTEXT_STRUCTURING_TASK_NAME = "aria.context.structure.v1"


def register_context_structuring_task(
    celery_app: Celery,
    consumer: ContextStructuringConsumer,
) -> None:
    @celery_app.task(
        name=CONTEXT_STRUCTURING_TASK_NAME,
        bind=False,
        autoretry_for=(),
        ignore_result=True,
    )
    def structure_context(payload: object) -> dict[str, str | None]:
        message = ContextStructuringJobMessage.from_payload(payload)
        result = asyncio.run(consumer.execute(message))
        return {"status": result.status, "error_code": result.error_code}
