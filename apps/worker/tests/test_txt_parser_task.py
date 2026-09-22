from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]

from app.application.txt_parser_consumer import ParserConsumerResult
from app.infrastructure.queue.parser_task import register_txt_parser_task
from app.tasks.txt_parser import run_controlled_txt_parser_message


def test_controlled_path_runs_one_explicit_message_without_registration() -> None:
    consumer = AsyncMock()
    consumer.execute.return_value = ParserConsumerResult(status="succeeded")

    result = run_controlled_txt_parser_message(
        consumer,
        {
            "message_version": "1",
            "outbox_event_id": str(uuid4()),
            "job_id": str(uuid4()),
        }
    )

    assert result == ParserConsumerResult(status="succeeded")
    consumer.execute.assert_awaited_once()


def test_registered_celery_task_has_exact_name_and_no_automatic_retry() -> None:
    consumer = AsyncMock()
    consumer.execute.return_value = ParserConsumerResult(status="already_completed")
    celery_app = Celery("test")
    register_txt_parser_task(celery_app, consumer)
    payload = {
        "message_version": "1",
        "outbox_event_id": str(uuid4()),
        "job_id": str(uuid4()),
    }

    result = celery_app.tasks["aria.context.parse.v1"].run(payload)

    assert result == {"status": "already_completed", "error_code": None}
    consumer.execute.assert_awaited_once()
    assert celery_app.tasks["aria.context.parse.v1"].autoretry_for == ()
