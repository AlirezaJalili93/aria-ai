import json
from io import StringIO
from uuid import UUID

from aria_observability import JobTraceContext, create_event_logger
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app


def _settings() -> ApiSettings:
    return ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")


def _app_with_log_stream(stream: StringIO) -> FastAPI:
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    return create_app(_settings(), event_logger=logger)


def test_request_ids_are_generated_returned_and_logged_as_structured_json() -> None:
    stream = StringIO()
    client = TestClient(_app_with_log_stream(stream))

    response = client.get("/health/live")

    request_id = response.headers["X-Request-ID"]
    correlation_id = response.headers["X-Correlation-ID"]
    UUID(request_id)
    UUID(correlation_id)

    event = json.loads(stream.getvalue().splitlines()[-1])
    assert event == {
        "timestamp": event["timestamp"],
        "level": "INFO",
        "service": "aria-api",
        "environment": "test",
        "app_version": "0.1.0",
        "release_commit_sha": None,
        "event_name": "http.request_completed",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "account_id": None,
        "project_id": None,
        "job_id": None,
        "route": "/health/live",
        "task_type": None,
        "duration_ms": event["duration_ms"],
        "status": 200,
        "error_code": None,
        "provider_request_id": None,
    }
    assert event["timestamp"].endswith("Z")
    assert event["duration_ms"] >= 0


def test_safe_client_trace_ids_are_preserved_and_unsafe_values_are_replaced() -> None:
    safe_request_id = "c11a58e5-546f-46e0-a68f-167e61f44971"
    safe_correlation_id = "06635353-20c7-4db4-a102-f790439f2ab4"
    client = TestClient(_app_with_log_stream(StringIO()))

    accepted = client.get(
        "/health/live",
        headers={
            "X-Request-ID": safe_request_id,
            "X-Correlation-ID": safe_correlation_id,
        },
    )
    replaced = client.get(
        "/health/live",
        headers={"X-Request-ID": "unsafe\nvalue", "X-Correlation-ID": "not-a-uuid"},
    )

    assert accepted.headers["X-Request-ID"] == safe_request_id
    assert accepted.headers["X-Correlation-ID"] == safe_correlation_id
    assert replaced.headers["X-Request-ID"] != "unsafe\nvalue"
    assert replaced.headers["X-Correlation-ID"] != "not-a-uuid"
    UUID(replaced.headers["X-Request-ID"])
    UUID(replaced.headers["X-Correlation-ID"])


def test_request_logging_never_records_headers_query_values_or_raw_content() -> None:
    stream = StringIO()
    client = TestClient(_app_with_log_stream(stream))
    secret = "secret-value-that-must-not-appear"

    response = client.get(
        f"/health/live?token={secret}",
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 200
    output = stream.getvalue()
    assert secret not in output
    assert "Authorization" not in output
    assert "token=" not in output

    unmatched_secret = "confidential-path-value"
    client.get(f"/{unmatched_secret}")
    assert unmatched_secret not in stream.getvalue()
    assert '"route":"/<unmatched>"' in stream.getvalue()


def test_request_context_builds_versioned_job_context_without_regeneration() -> None:
    stream = StringIO()
    app = _app_with_log_stream(stream)

    @app.get("/test/job-context")
    async def build_job_context() -> dict[str, object]:
        return JobTraceContext.from_current_request(
            job_id="b25dd8a3-ac65-4996-ab2f-e1a2a6d2263c",
            task_type="context.parse",
            payload_version="1.0",
            account_id="a720185c-49d2-442c-b70b-fd030fa7fd1f",
            project_id="4cb15eb2-a5f4-4b12-90f9-99d27c6cf185",
        ).to_message_context()

    correlation_id = "7b99d75a-d880-4c4d-97fd-d791b9d54f9b"
    response = TestClient(app).get(
        "/test/job-context", headers={"X-Correlation-ID": correlation_id}
    )

    assert response.status_code == 200
    assert response.json()["correlationId"] == correlation_id
    assert response.json()["payloadVersion"] == "1.0"
