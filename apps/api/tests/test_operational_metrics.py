from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from aria_observability import BufferedOperationalMetrics, MetricAttributePolicy
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import ApiSettings
from app.main import create_app


@dataclass
class CapturingBackend:
    records: list[tuple[str, str, int | float, dict[str, str]]] = field(
        default_factory=list
    )

    def add_counter(
        self, name: str, value: int | float, attributes: dict[str, str]
    ) -> None:
        self.records.append(("counter", name, value, dict(attributes)))

    def record_histogram(
        self, name: str, value: int | float, attributes: dict[str, str]
    ) -> None:
        self.records.append(("histogram", name, value, dict(attributes)))

    def shutdown(self, timeout_seconds: float) -> None:
        del timeout_seconds


class ExplodingMetrics:
    def record_http_request(self, **fields: object) -> None:
        del fields
        raise RuntimeError("telemetry unavailable")

    def shutdown(self, timeout_seconds: float) -> None:
        del timeout_seconds


def _settings() -> ApiSettings:
    return ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")


def test_http_metrics_use_route_templates_and_bounded_status_class() -> None:
    backend = CapturingBackend()
    metrics = BufferedOperationalMetrics(backend, queue_capacity=8)
    metrics.record_http_request(
        route="/api/v1/projects/{project_id}",
        method="GET",
        status_code=200,
        duration_ms=12.5,
    )
    metrics.shutdown(1)
    assert len(backend.records) == 2
    assert all(
        record[3]
        == {
            "route": "/api/v1/projects/{project_id}",
            "method": "GET",
            "status_class": "2xx",
        }
        for record in backend.records
    )


def test_unbounded_or_sensitive_metric_attributes_are_dropped() -> None:
    policy = MetricAttributePolicy(allowed_models=frozenset({"approved-model"}))
    assert policy.sanitize(
        "aria.http.server.requests",
        {"route": "/projects/123", "method": "GET", "status_class": "2xx"},
    ) is None
    assert policy.sanitize(
        "aria.worker.jobs", {"job_type": "context_parse", "status": "partial"}
    ) is None
    assert policy.sanitize(
        "aria.ai.provider.requests",
        {
            "workflow": "context_structuring",
            "provider": "provider-a",
            "model": "raw-provider-model",
            "status": "success",
        },
    ) is None
    assert policy.sanitize(
        "aria.ai.validation.failures",
        {
            "workflow": "context_structuring",
            "validation_kind": "schema",
            "project_id": "b25dd8a3-ac65-4996-ab2f-e1a2a6d2263c",
        },
    ) is None


def test_telemetry_failure_does_not_fail_api_request() -> None:
    app = create_app(_settings(), operational_metrics=ExplodingMetrics())  # type: ignore[arg-type]
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200


def test_otlp_configuration_is_explicit_and_staging_only() -> None:
    with pytest.raises(ValidationError, match="Incomplete OTLP metrics configuration"):
        ApiSettings(
            app_env="test",
            app_version="0.1.0",
            log_level="INFO",
            otel_exporter_otlp_endpoint="https://otlp.example.test",
        )

    hosted = {
        "app_version": "0.1.0",
        "log_level": "INFO",
        "public_app_url": "https://staging.example.test",
        "api_base_url": "https://api-staging.example.test/api/v1",
        "database_url": "postgresql://staging.example.test/aria",
        "queue_broker_url": "redis://queue-staging.example.test:6379/0",
        "storage_endpoint": "https://storage-staging.example.test",
        "storage_region": "eu-central-1",
        "storage_bucket": "aria-staging-artifacts",
        "storage_access_key": "test-access-key",
        "storage_secret_key": "test-secret-key",
        "auth_provider_url": "https://auth-staging.example.test/auth/v1",
        "auth_jwks_url": "https://auth-staging.example.test/auth/v1/.well-known/jwks.json",
        "auth_audience": "authenticated",
        "release_commit_sha": "a" * 40,
        "otel_exporter_otlp_endpoint": "https://otlp.example.test",
        "otel_exporter_otlp_headers": "Authorization=Basic test-secret",
        "otel_metric_export_timeout_seconds": 2,
        "otel_metric_export_interval_seconds": 15,
        "otel_metric_queue_capacity": 128,
    }
    assert ApiSettings(app_env="staging", **hosted).otel_metric_queue_capacity == 128
    with pytest.raises(ValidationError, match="Direct OTLP export is staging-only"):
        ApiSettings(app_env="production", **hosted)
