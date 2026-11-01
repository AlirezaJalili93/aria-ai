"""Explicit Local/Synthetic registration; never imported by the hosted bootstrap."""

from __future__ import annotations

import asyncio
from typing import Protocol

from aria_backend_application.preview_delivery import PreviewError
from celery import Celery  # type: ignore[import-untyped]

from app.application.preview_publication_runtime import (
    PERMANENT_PREVIEW_FAILURES,
    PREVIEW_TASK_NAME,
    PreviewPublicationMessage,
    PreviewPublicationResult,
)


class PreviewPublicationExecutor(Protocol):
    async def execute(self, message: PreviewPublicationMessage) -> PreviewPublicationResult: ...


def register_preview_publication_task(
    celery_app: Celery, executor: PreviewPublicationExecutor
) -> None:
    if PREVIEW_TASK_NAME in celery_app.tasks:
        raise PreviewError("FEATURE_NOT_ENABLED")

    @celery_app.task(
        name=PREVIEW_TASK_NAME,
        bind=False,
        shared=False,
        lazy=False,
        autoretry_for=(),
        max_retries=0,
        ignore_result=True,
    )
    def publish_preview(payload: object) -> dict[str, str | None]:
        try:
            message = PreviewPublicationMessage.from_payload(payload)
            result = asyncio.run(executor.execute(message))
            if (
                result.status in {"succeeded", "already_completed"} and result.error_code is None
            ) or (result.status == "failed" and result.error_code in PERMANENT_PREVIEW_FAILURES):
                return {"status": result.status, "error_code": result.error_code}
            raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True)
        except PreviewError as exc:
            raise PreviewError(exc.code, retryable=exc.retryable) from None
        except Exception:
            # Framework failure diagnostics must never include a raw storage/DB error.
            # This bounded failure does not schedule retry or create another Job.
            raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None
