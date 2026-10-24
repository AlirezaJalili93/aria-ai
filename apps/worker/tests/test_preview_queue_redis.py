"""Real loopback broker/task transport proof, not PostgreSQL/browser E2E."""

from __future__ import annotations

import asyncio
import os
import threading
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from aria_backend_application.preview_delivery import PreviewError
from celery import signals  # type: ignore[import-untyped]
from celery.contrib.testing.worker import start_worker  # type: ignore[import-untyped]
from pydantic import SecretStr
from redis import Redis
from test_preview_queue import Executor, event

from app.application.preview_publication_runtime import PREVIEW_TASK_NAME, PreviewPublicationResult
from app.core.config import QueueRuntimeConfiguration
from app.infrastructure.queue.celery_runtime import create_celery_app
from app.infrastructure.queue.preview_outbox_publisher import CeleryPreviewOutboxPublisher
from app.infrastructure.queue.preview_publication_task import register_preview_publication_task

TEST_QUEUE_BROKER_URL = os.environ.get("TEST_QUEUE_BROKER_URL")
pytestmark = pytest.mark.skipif(
    TEST_QUEUE_BROKER_URL is None, reason="Owned throwaway loopback Redis required"
)


@pytest.mark.parametrize("mode", ["success", "permanent", "recoverable"])
def test_actual_redis_delivery_uses_only_identifiers_and_no_consumer_retry(mode):
    assert TEST_QUEUE_BROKER_URL is not None
    target = urlsplit(TEST_QUEUE_BROKER_URL)
    assert target.scheme == "redis" and target.hostname == "127.0.0.1"
    queue = "preview-0102-" + str(uuid4())
    app = create_celery_app(
        QueueRuntimeConfiguration(
            broker_url=SecretStr(TEST_QUEUE_BROKER_URL),
            queue_name=queue,
            visibility_timeout_seconds=60,
            concurrency=1,
        )
    )
    executor = Executor(
        result=PreviewPublicationResult("failed", "PREVIEW_SOURCE_INVALID")
        if mode == "permanent"
        else None,
        failure=PreviewError("PREVIEW_STORAGE_ERROR", retryable=True)
        if mode == "recoverable"
        else None,
    )
    register_preview_publication_task(app, executor)
    task = app.tasks[PREVIEW_TASK_NAME]
    finished, outcomes = threading.Event(), []

    def complete(sender=None, state=None, **kwargs):
        if sender is task:
            outcomes.append(state)
            finished.set()

    signals.task_postrun.connect(complete, sender=task, weak=False)
    client = Redis.from_url(TEST_QUEUE_BROKER_URL)
    value = event()
    try:
        with start_worker(
            app,
            pool="solo",
            perform_ping_check=False,
            queues=[queue],
            loglevel="CRITICAL",
            logfile=os.devnull,
            shutdown_timeout=15,
            without_heartbeat=True,
        ):
            asyncio.run(CeleryPreviewOutboxPublisher(app, queue_name=queue).publish(value))
            assert finished.wait(15), "Controlled Preview task did not complete"
            assert len(executor.messages) == 1
            received = executor.messages[0]
            assert received.message_version == "1"
            assert received.outbox_event_id == value.id
            assert received.job_id == value.aggregate_id
            assert outcomes == ["FAILURE" if mode == "recoverable" else "SUCCESS"]
        assert task.autoretry_for == () and task.max_retries == 0
        assert app.conf.result_backend is None and task.ignore_result
        assert client.llen(queue) == 0
    finally:
        signals.task_postrun.disconnect(complete, sender=task)
        # Exact queue created by this test only; no FLUSHDB/FLUSHALL or shared queue removal.
        client.delete(queue)
        client.close()
        app.close()
