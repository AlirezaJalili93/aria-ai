import json
from io import StringIO

from aria_observability import JobTraceContext, bind_trace_context, create_event_logger

from app.core.config import WorkerSettings
from app.main import run_worker


class RuntimeProbe:
    def run(self) -> None:
        pass


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_worker_startup_uses_structured_logging_instead_of_print() -> None:
    stream = StringIO()
    settings = WorkerSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        queue_broker_url="redis://queue.test:6379/0",
        queue_name="aria-test-jobs",
        queue_visibility_timeout_seconds=60,
        worker_concurrency=1,
    )

    run_worker(settings, queue_runtime=RuntimeProbe(), event_logger=_logger(stream))

    event = json.loads(stream.getvalue())
    assert event["event_name"] == "worker.runtime_started"
    assert event["service"] == "aria-worker"
    assert event["environment"] == "test"
    assert event["status"] == "started"
    assert event["queue_adapter_configured"] is True


def test_job_context_preserves_correlation_through_worker_and_provider_boundary() -> None:
    message_context = {
        "jobId": "b25dd8a3-ac65-4996-ab2f-e1a2a6d2263c",
        "taskType": "context.parse",
        "payloadVersion": "1.0",
        "accountId": "a720185c-49d2-442c-b70b-fd030fa7fd1f",
        "projectId": "4cb15eb2-a5f4-4b12-90f9-99d27c6cf185",
        "correlationId": "7b99d75a-d880-4c4d-97fd-d791b9d54f9b",
    }
    job = JobTraceContext.from_message_context(message_context)
    provider = job.to_provider_context()
    stream = StringIO()

    with bind_trace_context(job.to_trace_context()):
        _logger(stream).emit("worker.job_started", task_type=job.task_type, status="running")

    event = json.loads(stream.getvalue())
    assert event["correlation_id"] == message_context["correlationId"]
    assert event["job_id"] == message_context["jobId"]
    assert provider.correlation_id == message_context["correlationId"]
    assert provider.job_id == message_context["jobId"]


def test_structured_logger_drops_unapproved_sensitive_fields() -> None:
    stream = StringIO()
    logger = _logger(stream)

    logger.emit(
        "worker.safe_event",
        status="ok",
        authorization="Bearer secret-token",
        raw_content="confidential project brief",
        prompt="full model prompt",
        share_token="raw-share-token",
    )

    output = stream.getvalue()
    assert "secret-token" not in output
    assert "confidential project brief" not in output
    assert "full model prompt" not in output
    assert "raw-share-token" not in output
    assert json.loads(output)["status"] == "ok"
