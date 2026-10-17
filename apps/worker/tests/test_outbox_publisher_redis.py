from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from celery import Celery  # type: ignore[import-untyped]
from pydantic import SecretStr
from redis import Redis

from app.application.outbox_delivery import ClaimedOutboxEvent, OutboxPublishError
from app.core.config import QueueRuntimeConfiguration
from app.infrastructure.queue.celery_runtime import create_celery_app
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher

TEST_QUEUE_BROKER_URL = os.environ.get("TEST_QUEUE_BROKER_URL")
pytestmark = pytest.mark.skipif(
    TEST_QUEUE_BROKER_URL is None,
    reason="TEST_QUEUE_BROKER_URL is required for real Redis integration evidence",
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


def _celery(broker_url: str, queue_name: str) -> Celery:
    configuration = QueueRuntimeConfiguration(
        broker_url=SecretStr(broker_url),
        queue_name=queue_name,
        visibility_timeout_seconds=60,
        concurrency=1,
    )
    return create_celery_app(configuration)


def test_redis_unavailable_then_recovery_publishes_same_logical_event_once() -> None:
    assert TEST_QUEUE_BROKER_URL is not None
    event = _event()
    unavailable = _celery("redis://127.0.0.1:1/15", "aria-unavailable")
    unavailable.conf.broker_connection_timeout = 1
    with pytest.raises(OutboxPublishError):
        asyncio.run(
            CeleryOutboxPublisher(unavailable, queue_name="aria-unavailable").publish(event)
        )

    queue_name = f"aria-relay-test-{uuid4()}"
    redis = Redis.from_url(TEST_QUEUE_BROKER_URL)
    redis.delete(queue_name)
    try:
        asyncio.run(
            CeleryOutboxPublisher(
                _celery(TEST_QUEUE_BROKER_URL, queue_name),
                queue_name=queue_name,
            ).publish(event)
        )
        assert redis.llen(queue_name) == 1
    finally:
        redis.delete(queue_name)
        redis.close()
