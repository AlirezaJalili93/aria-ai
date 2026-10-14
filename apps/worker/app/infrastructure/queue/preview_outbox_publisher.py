"""Opt-in Preview mapping for controlled composition, not the general Relay."""

from __future__ import annotations

import asyncio

from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from kombu.exceptions import OperationalError  # type: ignore[import-untyped]

from app.application.outbox_delivery import (
    ClaimedOutboxEvent,
    OutboxPublishError,
    UnknownOutboxEventError,
)
from app.application.preview_publication_runtime import (
    PREVIEW_EVENT_TYPE,
    PREVIEW_JOB_TYPE,
    PREVIEW_TASK_NAME,
)
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher, _job_message


class CeleryPreviewOutboxPublisher(CeleryOutboxPublisher):
    async def publish(self, event: ClaimedOutboxEvent) -> None:
        if event.event_type != PREVIEW_EVENT_TYPE:
            await super().publish(event)
            return
        if (
            event.delivery_channel != "job_queue"
            or event.aggregate_type != "job"
            or PREVIEW_TASK_NAME not in self._celery_app.tasks
        ):
            raise UnknownOutboxEventError
        message = _job_message(event, expected_job_type=PREVIEW_JOB_TYPE)
        if message["job_id"] != str(event.aggregate_id):
            raise UnknownOutboxEventError
        try:
            await asyncio.to_thread(
                self._celery_app.send_task,
                PREVIEW_TASK_NAME,
                args=[message],
                queue=self._queue_name,
                retry=False,
            )
        except (CeleryError, OperationalError, OSError):
            raise OutboxPublishError from None
