from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.txt_parser_consumer import ParserConsumerResult
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
