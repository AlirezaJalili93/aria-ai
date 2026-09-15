from dataclasses import dataclass
from typing import Protocol

from aria_observability import (
    OperationalMetrics,
    OtlpMetricsConfiguration,
    StructuredEventLogger,
    create_event_logger,
    create_otlp_operational_metrics,
)

from app.core.config import WorkerSettings, load_worker_settings
from app.infrastructure.queue.celery_runtime import create_celery_queue_runtime


class QueueRuntime(Protocol):
    def run(self) -> None: ...


@dataclass(frozen=True, slots=True)
class WorkerBootstrap:
    queue_adapter_configured: bool
    service_name: str = "aria-worker"
    environment: str = "local"
    app_version: str = "0.1.0"


def bootstrap_worker(settings: WorkerSettings | None = None) -> WorkerBootstrap:
    resolved_settings = settings or load_worker_settings()
    resolved_settings.require_queue_runtime_configuration()
    return WorkerBootstrap(
        queue_adapter_configured=True,
        environment=resolved_settings.app_env,
        app_version=resolved_settings.app_version,
    )


def run_worker(
    settings: WorkerSettings | None = None,
    queue_runtime: QueueRuntime | None = None,
    event_logger: StructuredEventLogger | None = None,
    operational_metrics: OperationalMetrics | None = None,
) -> None:
    resolved_settings = settings or load_worker_settings()
    worker = bootstrap_worker(resolved_settings)
    resolved_queue_runtime = queue_runtime or create_celery_queue_runtime(
        resolved_settings.require_queue_runtime_configuration(),
        log_level=resolved_settings.log_level,
    )
    metrics_configuration = _metrics_configuration(resolved_settings)
    resolved_operational_metrics = operational_metrics or create_otlp_operational_metrics(
        service=worker.service_name,
        environment=worker.environment,
        app_version=worker.app_version,
        configuration=metrics_configuration,
    )
    resolved_event_logger = event_logger or create_event_logger(
        service=worker.service_name,
        environment=worker.environment,
        app_version=worker.app_version,
        release_commit_sha=resolved_settings.release_commit_sha,
        level=resolved_settings.log_level,
    )
    resolved_event_logger.emit(
        "worker.runtime_started",
        status="started",
        queue_adapter_configured=worker.queue_adapter_configured,
    )
    try:
        resolved_queue_runtime.run()
    finally:
        resolved_operational_metrics.shutdown(
            metrics_configuration.export_timeout_seconds if metrics_configuration else 0
        )


def _metrics_configuration(settings: WorkerSettings) -> OtlpMetricsConfiguration | None:
    if settings.otel_exporter_otlp_endpoint is None:
        return None
    assert settings.otel_exporter_otlp_headers is not None
    assert settings.otel_metric_export_timeout_seconds is not None
    assert settings.otel_metric_export_interval_seconds is not None
    assert settings.otel_metric_queue_capacity is not None
    allowed_models = frozenset(
        value.strip()
        for value in (settings.otel_metric_allowed_models or "").split(",")
        if value.strip()
    )
    return OtlpMetricsConfiguration(
        endpoint=str(settings.otel_exporter_otlp_endpoint),
        headers=settings.otel_exporter_otlp_headers.get_secret_value(),
        export_timeout_seconds=float(settings.otel_metric_export_timeout_seconds),
        export_interval_seconds=float(settings.otel_metric_export_interval_seconds),
        queue_capacity=settings.otel_metric_queue_capacity,
        allowed_models=allowed_models,
    )


if __name__ == "__main__":
    run_worker()
