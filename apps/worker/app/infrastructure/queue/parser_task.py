from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from app.application.txt_parser_consumer import TxtParserConsumer
from app.tasks.txt_parser import run_controlled_txt_parser_message


def register_txt_parser_task(celery_app: Celery, consumer: TxtParserConsumer) -> None:
    @celery_app.task(
        name="aria.context.parse.v1",
        bind=False,
        autoretry_for=(),
        ignore_result=True,
    )
    def parse_context(payload: object) -> dict[str, str | None]:
        result = run_controlled_txt_parser_message(consumer, payload)
        return {"status": result.status, "error_code": result.error_code}
