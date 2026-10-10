from __future__ import annotations

import asyncio

from celery import Celery  # type: ignore[import-untyped]

from app.application.gap_detection_consumer import (
    GapDetectionConsumer,
    GapDetectionJobMessage,
)

GAP_DETECTION_TASK_NAME = "aria.gaps.detect.v1"


def register_gap_detection_task(
    celery_app: Celery, consumer: GapDetectionConsumer
) -> None:
    """Register only in a controlled test runtime; hosted composition omits this call."""

    @celery_app.task(
        name=GAP_DETECTION_TASK_NAME,
        bind=False,
        autoretry_for=(),
        ignore_result=True,
    )
    def detect_gaps(payload: object) -> dict[str, str | None]:
        message = GapDetectionJobMessage.from_payload(payload)
        result = asyncio.run(consumer.execute(message))
        return {"status": result.status, "error_code": result.error_code}
