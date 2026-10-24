from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]

from app.application.requirement_generation_consumer import (
    RequirementGenerationConsumerResult,
)
from app.infrastructure.queue.requirement_generation_task import (
    REQUIREMENT_GENERATION_TASK_NAME,
    register_requirement_generation_task,
)


class _Consumer:
    async def execute(self, message):
        assert message.message_version == "1"
        return RequirementGenerationConsumerResult(status="succeeded")


def test_controlled_task_has_no_celery_automatic_retry() -> None:
    celery_app = Celery("requirement-test", broker="memory://")
    register_requirement_generation_task(
        celery_app, _Consumer()  # type: ignore[arg-type]
    )
    payload = {
        "message_version": "1",
        "outbox_event_id": str(uuid4()),
        "job_id": str(uuid4()),
    }
    result = celery_app.tasks[REQUIREMENT_GENERATION_TASK_NAME].run(payload)
    assert result == {"status": "succeeded", "error_code": None}
    assert celery_app.tasks[REQUIREMENT_GENERATION_TASK_NAME].autoretry_for == ()


def test_hosted_worker_does_not_receive_requirement_task_registration() -> None:
    runtime = Mock()
    assert REQUIREMENT_GENERATION_TASK_NAME not in runtime.mock_calls
