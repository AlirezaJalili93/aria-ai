from __future__ import annotations

import asyncio
from collections.abc import Mapping
from uuid import UUID

from celery import Celery  # type: ignore[import-untyped]
from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from kombu.exceptions import OperationalError  # type: ignore[import-untyped]

from app.application.outbox_delivery import (
    ClaimedOutboxEvent,
    OutboxPublishError,
    UnknownOutboxEventError,
)

PARSER_EVENT_TYPE = "context_added.v1"
PARSER_JOB_TYPE = "context_source_parse"
PARSER_MESSAGE_VERSION = "1"
PARSER_TASK_NAME = "aria.context.parse.v1"
CONTEXT_STRUCTURING_EVENT_TYPE = "context.structuring_requested.v1"
CONTEXT_STRUCTURING_JOB_TYPE = "context_structuring"
CONTEXT_STRUCTURING_TASK_NAME = "aria.context.structure.v1"


class CeleryOutboxPublisher:
    def __init__(self, celery_app: Celery, *, queue_name: str) -> None:
        self._celery_app = celery_app
        self._queue_name = queue_name

    async def publish(self, event: ClaimedOutboxEvent) -> None:
        if event.delivery_channel != "job_queue":
            raise UnknownOutboxEventError
        if event.event_type == PARSER_EVENT_TYPE:
            task_name = PARSER_TASK_NAME
            message = _job_message(event, expected_job_type=PARSER_JOB_TYPE)
        elif event.event_type == CONTEXT_STRUCTURING_EVENT_TYPE:
            task_name = CONTEXT_STRUCTURING_TASK_NAME
            message = _job_message(event, expected_job_type=CONTEXT_STRUCTURING_JOB_TYPE)
        else:
            raise UnknownOutboxEventError
        try:
            await asyncio.to_thread(
                self._celery_app.send_task,
                task_name,
                args=[message],
                queue=self._queue_name,
                retry=False,
            )
        except (CeleryError, OperationalError, OSError):
            raise OutboxPublishError from None


def _job_message(
    event: ClaimedOutboxEvent,
    *,
    expected_job_type: str,
) -> dict[str, str]:
    payload: Mapping[str, object] = event.payload
    parser_payload_fields = {
        "jobId",
        "taskType",
        "payloadVersion",
        "accountId",
        "projectId",
        "correlationId",
    }
    structuring_payload_fields = {"jobId", "taskType", "payloadVersion"}
    expected_fields = (
        parser_payload_fields
        if expected_job_type == PARSER_JOB_TYPE
        else structuring_payload_fields
    )
    if set(payload) != expected_fields:
        raise UnknownOutboxEventError
    if payload["taskType"] != expected_job_type or payload["payloadVersion"] != "1":
        raise UnknownOutboxEventError
    try:
        job_id = UUID(str(payload["jobId"]))
        if expected_job_type == PARSER_JOB_TYPE:
            UUID(str(payload["accountId"]))
            UUID(str(payload["projectId"]))
            UUID(str(payload["correlationId"]))
    except (TypeError, ValueError):
        raise UnknownOutboxEventError from None
    return {
        "message_version": PARSER_MESSAGE_VERSION,
        "outbox_event_id": str(event.id),
        "job_id": str(job_id),
    }
