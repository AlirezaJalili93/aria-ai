import json
from io import StringIO
from uuid import UUID

from aria_observability import (
    JobTraceContext,
    bind_trace_context,
    create_event_logger,
    current_trace_context,
    enrich_trace_context,
    resolve_http_trace_context,
)
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
        "schema_version": "1",
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


def test_pure_asgi_middleware_preserves_downstream_trace_enrichment() -> None:
    stream = StringIO()
    app = _app_with_log_stream(stream)
    job_id = "b25dd8a3-ac65-4996-ab2f-e1a2a6d2263c"

    @app.get("/test/enriched-trace")
    async def enriched_trace() -> dict[str, str]:
        enrich_trace_context(job_id=job_id)
        return {"job_id": job_id}

    response = TestClient(app).get("/test/enriched-trace")

    assert response.status_code == 200
    completion = json.loads(stream.getvalue().splitlines()[-1])
    assert completion["event_name"] == "http.request_completed"
    assert completion["job_id"] == job_id


def test_trace_enrichment_validates_ids_and_stays_inside_bound_context() -> None:
    account_id = "a720185c-49d2-442c-b70b-fd030fa7fd1f"
    project_id = "4cb15eb2-a5f4-4b12-90f9-99d27c6cf185"
    job_id = "b25dd8a3-ac65-4996-ab2f-e1a2a6d2263c"

    with bind_trace_context(resolve_http_trace_context(None, None)):
        enriched = enrich_trace_context(
            account_id=account_id,
            project_id=project_id,
            job_id=job_id,
        )

        assert current_trace_context() == enriched
        assert enriched.account_id == account_id
        assert enriched.project_id == project_id
        assert enriched.job_id == job_id

    assert current_trace_context() is None


def test_unhandled_exception_logs_safe_diagnostic_metadata_without_message() -> None:
    stream = StringIO()
    app = _app_with_log_stream(stream)
    secret_message = "sensitive-exception-message"

    @app.get("/test/unhandled")
    async def unhandled() -> None:
        raise ValueError(secret_message)

    response = TestClient(app, raise_server_exceptions=False).get("/test/unhandled")

    assert response.status_code == 500
    failure = json.loads(stream.getvalue().splitlines()[-1])
    assert failure["event_name"] == "http.request_failed"
    assert failure["exception_type"] == "ValueError"
    assert failure["component"] == "http.middleware"
    assert failure["operation"] == "request"
    assert secret_message not in stream.getvalue()


def test_logging_schema_allows_safe_ai_metadata_and_discards_raw_content() -> None:
    stream = StringIO()
    logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    secret_prompt = "raw-customer-prompt"
    secret_response = "raw-provider-response"

    logger.emit(
        "ai.provider_completed",
        provider="provider-a",
        model="model-1",
        workflow="context-structuring",
        attempt=2,
        latency_ms=125.25,
        status="succeeded",
        error_code="NONE",
        input_tokens=120,
        output_tokens=80,
        estimated_cost=0.0125,
        prompt=secret_prompt,
        response=secret_response,
    )

    event = json.loads(stream.getvalue())
    assert event["schema_version"] == "1"
    assert event["provider"] == "provider-a"
    assert event["model"] == "model-1"
    assert event["workflow"] == "context-structuring"
    assert event["attempt"] == 2
    assert event["latency_ms"] == 125.25
    assert event["input_tokens"] == 120
    assert event["output_tokens"] == 80
    assert event["estimated_cost"] == 0.0125
    assert secret_prompt not in stream.getvalue()
    assert secret_response not in stream.getvalue()
