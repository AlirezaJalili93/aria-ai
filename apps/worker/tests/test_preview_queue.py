from __future__ import annotations

import asyncio
import traceback
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from aria_backend_application.preview_delivery import PreviewError
from celery import Celery  # type: ignore[import-untyped]

from app.application.outbox_delivery import (
    ClaimedOutboxEvent,
    OutboxPublishError,
    UnknownOutboxEventError,
)
from app.application.preview_publication_runtime import (
    PREVIEW_EVENT_TYPE,
    PREVIEW_JOB_TYPE,
    PREVIEW_TASK_NAME,
    PreviewPublicationMessage,
    PreviewPublicationResult,
)
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher
from app.infrastructure.queue.preview_outbox_publisher import CeleryPreviewOutboxPublisher
from app.infrastructure.queue.preview_publication_task import register_preview_publication_task


class Executor:
    def __init__(self, result=None, failure=None):
        self.result = result or PreviewPublicationResult("succeeded")
        self.failure = failure
        self.messages = []

    async def execute(self, message):
        self.messages.append(message)
        if self.failure is not None:
            raise self.failure
        return self.result


def application():
    app = Celery("preview-test-" + str(uuid4()), broker="memory://", set_as_current=False)
    app.conf.update(task_acks_late=True, task_reject_on_worker_lost=True, task_ignore_result=True)
    return app


def event():
    now, job = datetime.now(UTC), uuid4()
    return ClaimedOutboxEvent(
        id=uuid4(),
        account_id=uuid4(),
        aggregate_type="job",
        aggregate_id=job,
        event_type=PREVIEW_EVENT_TYPE,
        delivery_channel="job_queue",
        payload={"jobId": str(job), "taskType": PREVIEW_JOB_TYPE, "payloadVersion": "1"},
        delivery_attempt=1,
        claim_id=uuid4(),
        claimed_at=now,
        lease_until=now + timedelta(seconds=30),
        created_at=now,
        reclaimed=False,
    )


def message(value):
    return {
        "message_version": "1",
        "outbox_event_id": str(value.id),
        "job_id": str(value.aggregate_id),
    }


def test_task_is_app_local_and_no_retry_or_persistent_result():
    executor = Executor()
    with application() as controlled:
        register_preview_publication_task(controlled, executor)
        task = controlled.tasks[PREVIEW_TASK_NAME]
        assert task.autoretry_for == ()
        assert task.max_retries == 0
        assert task.ignore_result is True
        assert task.acks_late is True
        assert task.reject_on_worker_lost is True
        assert controlled.conf.result_backend is None
        with application() as ordinary:
            assert PREVIEW_TASK_NAME not in ordinary.tasks
            register_preview_publication_task(ordinary, Executor())
            assert ordinary.tasks[PREVIEW_TASK_NAME] is not task


def test_duplicate_registration_does_not_silently_replace_executor():
    with application() as app:
        original = Executor()
        register_preview_publication_task(app, original)
        with pytest.raises(PreviewError) as caught:
            register_preview_publication_task(app, Executor())
        assert caught.value.code == "FEATURE_NOT_ENABLED"
        app.tasks[PREVIEW_TASK_NAME].run(message(event()))
        assert len(original.messages) == 1


@pytest.mark.parametrize(
    "result",
    [
        PreviewPublicationResult("succeeded"),
        PreviewPublicationResult("already_completed"),
        PreviewPublicationResult("failed", "PREVIEW_SOURCE_INVALID"),
        PreviewPublicationResult("failed", "PREVIEW_SOURCE_UNSUPPORTED"),
        PreviewPublicationResult("failed", "PREVIEW_DELIVERY_CONFLICT"),
    ],
)
def test_task_invokes_existing_runtime_once_and_returns_only_safe_outcome(result):
    executor, value = Executor(result=result), event()
    with application() as app:
        register_preview_publication_task(app, executor)
        outcome = app.tasks[PREVIEW_TASK_NAME].run(message(value))
    assert outcome == {"status": result.status, "error_code": result.error_code}
    assert executor.messages == [PreviewPublicationMessage("1", value.id, value.aggregate_id)]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"message_version": "2", "outbox_event_id": str(uuid4()), "job_id": str(uuid4())},
        {"message_version": "1", "outbox_event_id": "bad", "job_id": str(uuid4())},
        {
            "message_version": "1",
            "outbox_event_id": str(uuid4()),
            "job_id": str(uuid4()),
            "token": "synthetic-secret-marker",
        },
    ],
)
def test_invalid_queue_payload_never_reaches_executor_or_diagnostics(payload, caplog):
    executor = Executor()
    with application() as app:
        register_preview_publication_task(app, executor)
        with pytest.raises(PreviewError) as caught:
            app.tasks[PREVIEW_TASK_NAME].run(payload)
    assert caught.value.code == "VALIDATION_FAILED"
    assert executor.messages == []
    assert "synthetic-secret-marker" not in str(caught.value) + caplog.text


@pytest.mark.parametrize(
    "failure",
    [
        PreviewError("PREVIEW_STORAGE_ERROR", retryable=True),
        RuntimeError("synthetic-private-error-marker"),
    ],
)
def test_failure_is_bounded_without_retry_or_raw_error_leak(failure, caplog):
    executor = Executor(failure=failure)
    with application() as app:
        register_preview_publication_task(app, executor)
        with pytest.raises(PreviewError) as caught:
            app.tasks[PREVIEW_TASK_NAME].run(message(event()))
    assert len(executor.messages) == 1
    assert caught.value.retryable
    expected = (
        failure.code if isinstance(failure, PreviewError) else "PREVIEW_FINALIZATION_RECOVERABLE"
    )
    assert caught.value.code == expected
    rendered = "".join(traceback.format_exception(caught.value))
    assert "synthetic-private-error-marker" not in rendered + caplog.text


@pytest.mark.parametrize(
    "result",
    [
        PreviewPublicationResult("succeeded", "synthetic-private-output-marker"),
        PreviewPublicationResult("failed", "synthetic-private-output-marker"),
        PreviewPublicationResult("failed"),
    ],
)
def test_executor_result_cannot_expose_noncontract_metadata(result):
    with application() as app:
        register_preview_publication_task(app, Executor(result=result))
        with pytest.raises(PreviewError) as caught:
            app.tasks[PREVIEW_TASK_NAME].run(message(event()))
        assert caught.value.code == "PREVIEW_FINALIZATION_RECOVERABLE"
        assert "synthetic-private-output-marker" not in str(caught.value)


def test_controlled_publisher_maps_only_identifier_envelope_without_publish_retry():
    with application() as app:
        register_preview_publication_task(app, Executor())
        app.send_task = Mock()
        value = event()
        asyncio.run(CeleryPreviewOutboxPublisher(app, queue_name="preview-test").publish(value))
        app.send_task.assert_called_once_with(
            PREVIEW_TASK_NAME,
            args=[message(value)],
            queue="preview-test",
            retry=False,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"delivery_channel": "domain_event"},
        {"event_type": "unknown.v1"},
        {"aggregate_type": "project"},
        {"aggregate_id": uuid4()},
        {"payload": {"jobId": str(uuid4()), "taskType": "other", "payloadVersion": "1"}},
        {"payload": {"jobId": str(uuid4()), "taskType": PREVIEW_JOB_TYPE, "payloadVersion": "2"}},
        {
            "payload": {
                "jobId": str(uuid4()),
                "taskType": PREVIEW_JOB_TYPE,
                "payloadVersion": "1",
                "context": "synthetic-private-input-marker",
            }
        },
    ],
)
def test_invalid_publish_mapping_never_sends_to_broker(change):
    with application() as app:
        register_preview_publication_task(app, Executor())
        app.send_task = Mock()
        with pytest.raises(UnknownOutboxEventError):
            asyncio.run(
                CeleryPreviewOutboxPublisher(app, queue_name="preview-test").publish(
                    replace(event(), **change)
                )
            )
        app.send_task.assert_not_called()


def test_general_publisher_remains_preview_disabled_and_missing_task_fails_closed():
    with application() as app:
        app.send_task = Mock()
        value = event()
        for publisher in [
            CeleryOutboxPublisher(app, queue_name="ordinary-test"),
            CeleryPreviewOutboxPublisher(app, queue_name="preview-test"),
        ]:
            with pytest.raises(UnknownOutboxEventError):
                asyncio.run(publisher.publish(value))
        app.send_task.assert_not_called()


def test_transport_failure_exposes_no_provider_or_broker_diagnostics():
    with application() as app:
        register_preview_publication_task(app, Executor())
        app.send_task = Mock(side_effect=OSError("synthetic-broker-secret-marker"))
        with pytest.raises(OutboxPublishError) as caught:
            asyncio.run(
                CeleryPreviewOutboxPublisher(app, queue_name="preview-test").publish(event())
            )
        assert "synthetic-broker-secret-marker" not in "".join(
            traceback.format_exception(caught.value)
        )
