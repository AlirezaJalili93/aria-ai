from __future__ import annotations

from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from aria_observability.operational_metrics import (
    AI_COST_TOTAL,
    AI_PROVIDER_DURATION,
    AI_PROVIDER_REQUEST_COUNT,
    AI_VALIDATION_FAILURE_COUNT,
    HTTP_REQUEST_COUNT,
    HTTP_REQUEST_DURATION,
    OUTBOX_PUBLISH_COUNT,
    WORKER_JOB_COUNT,
    WORKER_JOB_DURATION,
    BufferedOperationalMetrics,
    MetricAttributes,
    MetricBackend,
    MetricValue,
    NoOpOperationalMetrics,
    OperationalMetrics,
)


@dataclass(frozen=True, slots=True)
class OtlpMetricsConfiguration:
    endpoint: str
    headers: str
    export_timeout_seconds: float
    export_interval_seconds: float
    queue_capacity: int
    allowed_models: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.endpoint.startswith("https://"):
            raise ValueError("OTLP endpoint must use HTTPS")
        if "\r" in self.headers or "\n" in self.headers:
            raise ValueError("OTLP headers must not contain line breaks")
        if self.export_timeout_seconds <= 0 or self.export_interval_seconds <= 0:
            raise ValueError("OTLP timing values must be positive")
        if self.queue_capacity < 1:
            raise ValueError("OTLP metric queue capacity must be positive")


class OpenTelemetryMetricBackend(MetricBackend):
    """OTLP/HTTP adapter; OpenTelemetry types remain inside Infrastructure."""

    def __init__(self, provider: MeterProvider) -> None:
        self._provider = provider
        meter = provider.get_meter("aria.operational", "1")
        self._counters = {
            HTTP_REQUEST_COUNT: meter.create_counter(HTTP_REQUEST_COUNT),
            WORKER_JOB_COUNT: meter.create_counter(WORKER_JOB_COUNT),
            OUTBOX_PUBLISH_COUNT: meter.create_counter(OUTBOX_PUBLISH_COUNT),
            AI_PROVIDER_REQUEST_COUNT: meter.create_counter(AI_PROVIDER_REQUEST_COUNT),
            AI_VALIDATION_FAILURE_COUNT: meter.create_counter(AI_VALIDATION_FAILURE_COUNT),
            AI_COST_TOTAL: meter.create_counter(AI_COST_TOTAL, unit="USD"),
        }
        self._histograms = {
            HTTP_REQUEST_DURATION: meter.create_histogram(
                HTTP_REQUEST_DURATION, unit="ms"
            ),
            WORKER_JOB_DURATION: meter.create_histogram(WORKER_JOB_DURATION, unit="ms"),
            AI_PROVIDER_DURATION: meter.create_histogram(AI_PROVIDER_DURATION, unit="ms"),
        }

    def add_counter(
        self, name: str, value: MetricValue, attributes: MetricAttributes
    ) -> None:
        self._counters[name].add(value, attributes=attributes)

    def record_histogram(
        self, name: str, value: MetricValue, attributes: MetricAttributes
    ) -> None:
        self._histograms[name].record(value, attributes=attributes)

    def shutdown(self, timeout_seconds: float) -> None:
        self._provider.shutdown(timeout_millis=max(0, int(timeout_seconds * 1000)))


def create_otlp_operational_metrics(
    *,
    service: str,
    environment: str,
    app_version: str,
    configuration: OtlpMetricsConfiguration | None,
) -> OperationalMetrics:
    """Build a staging OTLP pipeline, or fail open to a no-op implementation."""

    if configuration is None:
        return NoOpOperationalMetrics()
    try:
        exporter = OTLPMetricExporter(
            endpoint=configuration.endpoint.rstrip("/") + "/v1/metrics",
            headers=_parse_headers(configuration.headers),
            timeout=configuration.export_timeout_seconds,
        )
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=int(configuration.export_interval_seconds * 1000),
            export_timeout_millis=int(configuration.export_timeout_seconds * 1000),
        )
        provider = MeterProvider(
            metric_readers=[reader],
            resource=Resource.create(
                {
                    "service.name": service,
                    "deployment.environment.name": environment,
                    "service.version": app_version,
                }
            ),
        )
        return BufferedOperationalMetrics(
            OpenTelemetryMetricBackend(provider),
            queue_capacity=configuration.queue_capacity,
            allowed_models=configuration.allowed_models,
        )
    except Exception:  # noqa: BLE001 -- exporter bootstrap must be fail-open
        return NoOpOperationalMetrics()


def _parse_headers(raw_headers: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        name, separator, value = item.partition("=")
        if not separator or not name.strip() or not value.strip():
            raise ValueError("OTLP headers must use comma-separated name=value entries")
        headers[name.strip()] = value.strip()
    return headers
