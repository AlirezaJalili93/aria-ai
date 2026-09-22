from __future__ import annotations

import asyncio

from app.application.txt_parser_consumer import (
    ParserConsumerResult,
    ParserJobMessage,
    TxtParserConsumer,
)


def run_controlled_txt_parser_message(
    consumer: TxtParserConsumer,
    payload: object,
) -> ParserConsumerResult:
    """Run one explicitly supplied delivery without registration, scheduling or retry."""

    message = ParserJobMessage.from_payload(payload)
    return asyncio.run(consumer.execute(message))
