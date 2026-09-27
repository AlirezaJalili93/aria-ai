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
REQUIREMENT_GENERATION_EVENT_TYPE = "requirement.generation_requested.v1"
REQUIREMENT_GENERATION_JOB_TYPE = "requirement_generation"
REQUIREMENT_GENERATION_TASK_NAME = "aria.requirements.generate.v1"
GAP_DETECTION_EVENT_TYPE = "gap.detection_requested.v1"
GAP_DETECTION_JOB_TYPE = "gap_detection"
GAP_DETECTION_TASK_NAME = "aria.gaps.detect.v1"
SCOPE_GENERATION_EVENT_TYPE = "scope.generation_requested.v1"
SCOPE_GENERATION_JOB_TYPE = "scope_generation"
SCOPE_GENERATION_TASK_NAME = "aria.scope.generate.v1"


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
        elif event.event_type == REQUIREMENT_GENERATION_EVENT_TYPE:
            task_name = REQUIREMENT_GENERATION_TASK_NAME
            message = _job_message(event, expected_job_type=REQUIREMENT_GENERATION_JOB_TYPE)
        elif event.event_type == GAP_DETECTION_EVENT_TYPE:
            task_name = GAP_DETECTION_TASK_NAME
            message = _job_message(event, expected_job_type=GAP_DETECTION_JOB_TYPE)
        elif event.event_type == SCOPE_GENERATION_EVENT_TYPE:
            task_name = SCOPE_GENERATION_TASK_NAME
            message = _job_message(event, expected_job_type=SCOPE_GENERATION_JOB_TYPE)
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
    identifier_only_payload_fields = {"jobId", "taskType", "payloadVersion"}
    expected_fields = (
        parser_payload_fields
        if expected_job_type == PARSER_JOB_TYPE
        else identifier_only_payload_fields
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
