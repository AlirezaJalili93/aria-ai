from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.application.outbox_delivery import ClaimedOutboxEvent, UnknownOutboxEventError
from app.infrastructure.queue.outbox_publisher import (
    CONTEXT_STRUCTURING_TASK_NAME,
    PARSER_TASK_NAME,
    CeleryOutboxPublisher,
)


def _event() -> ClaimedOutboxEvent:
    now = datetime.now(UTC)
    return ClaimedOutboxEvent(
        id=uuid4(),
        account_id=uuid4(),
        aggregate_type="context_source",
        aggregate_id=uuid4(),
        event_type="context_added.v1",
        delivery_channel="job_queue",
        payload={
            "jobId": str(uuid4()),
            "taskType": "context_source_parse",
            "payloadVersion": "1",
            "accountId": str(uuid4()),
            "projectId": str(uuid4()),
            "correlationId": str(uuid4()),
        },
        delivery_attempt=1,
        claim_id=uuid4(),
        claimed_at=now,
        lease_until=now + timedelta(seconds=30),
        created_at=now,
        reclaimed=False,
    )


def test_publisher_maps_only_approved_event_to_minimal_parser_envelope() -> None:
    celery_app = Mock()
    event = _event()
    publisher = CeleryOutboxPublisher(celery_app, queue_name="aria-test-jobs")

    asyncio.run(publisher.publish(event))

    celery_app.send_task.assert_called_once_with(
        PARSER_TASK_NAME,
        args=[
            {
                "message_version": "1",
                "outbox_event_id": str(event.id),
                "job_id": event.payload["jobId"],
            }
        ],
        queue="aria-test-jobs",
        retry=False,
    )


def test_publisher_maps_context_structuring_to_minimal_identifier_only_envelope() -> None:
    celery_app = Mock()
    event = _event()
    values = {field: getattr(event, field) for field in event.__dataclass_fields__}
    values.update(
        event_type="context.structuring_requested.v1",
        aggregate_type="project",
        payload={
            "jobId": str(uuid4()),
            "taskType": "context_structuring",
            "payloadVersion": "1",
        },
    )
    structuring_event = ClaimedOutboxEvent(**values)  # type: ignore[arg-type]
    publisher = CeleryOutboxPublisher(celery_app, queue_name="aria-test-jobs")

    asyncio.run(publisher.publish(structuring_event))

    celery_app.send_task.assert_called_once_with(
        CONTEXT_STRUCTURING_TASK_NAME,
        args=[
            {
                "message_version": "1",
                "outbox_event_id": str(structuring_event.id),
                "job_id": structuring_event.payload["jobId"],
            }
        ],
        queue="aria-test-jobs",
        retry=False,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"event_type": "unknown.v1"},
        {"delivery_channel": "domain_event"},
        {"payload": {"jobId": str(uuid4())}},
    ],
)
def test_publisher_fails_closed_for_unknown_mapping_or_envelope(change: dict[str, object]) -> None:
    event = _event()
    values = {field: getattr(event, field) for field in event.__dataclass_fields__}
    values.update(change)
    publisher = CeleryOutboxPublisher(Mock(), queue_name="aria-test-jobs")

    with pytest.raises(UnknownOutboxEventError):
        asyncio.run(publisher.publish(ClaimedOutboxEvent(**values)))  # type: ignore[arg-type]
