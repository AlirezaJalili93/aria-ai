from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]

from app.application.context_structuring_consumer import ContextStructuringConsumerResult
from app.infrastructure.queue.context_structuring_task import (
    CONTEXT_STRUCTURING_TASK_NAME,
    register_context_structuring_task,
)


class _Consumer:
    def __init__(self) -> None:
        self.message = None

    async def execute(self, message):
        self.message = message
        return ContextStructuringConsumerResult(status="succeeded")


def test_celery_task_has_no_automatic_retry_and_uses_minimal_envelope() -> None:
    celery_app = Celery("test")
    consumer = _Consumer()
    register_context_structuring_task(
        celery_app,
        consumer,  # type: ignore[arg-type]
    )
    payload = {
        "message_version": "1",
        "outbox_event_id": str(uuid4()),
        "job_id": str(uuid4()),
    }

    result = celery_app.tasks[CONTEXT_STRUCTURING_TASK_NAME].run(payload)

    assert result == {"status": "succeeded", "error_code": None}
    assert consumer.message is not None
    assert celery_app.tasks[CONTEXT_STRUCTURING_TASK_NAME].autoretry_for == ()
    assert Mock().called is False
