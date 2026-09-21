import asyncio
import sys
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
from app.infrastructure.queue.parser_task import register_txt_parser_task
from app.runtime.outbox_relay import run_outbox_relay
from app.runtime.txt_parser import build_txt_parser_consumer


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
    resolved_queue_runtime: QueueRuntime
    if queue_runtime is None:
        resolved_queue_runtime = create_celery_queue_runtime(
            resolved_settings.require_queue_runtime_configuration(),
            log_level=resolved_settings.log_level,
        )
        register_txt_parser_task(
            resolved_queue_runtime.celery_app,
            build_txt_parser_consumer(resolved_settings, resolved_event_logger),
        )
    else:
        resolved_queue_runtime = queue_runtime
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


def run_relay(settings: WorkerSettings | None = None) -> None:
    resolved_settings = settings or load_worker_settings()
    worker = bootstrap_worker(resolved_settings)
    if resolved_settings.database_url is None:
        raise ValueError("Missing Outbox Relay configuration: database_url")
    metrics_configuration = _metrics_configuration(resolved_settings)
    operational_metrics = create_otlp_operational_metrics(
        service=worker.service_name,
        environment=worker.environment,
        app_version=worker.app_version,
        configuration=metrics_configuration,
    )
    event_logger = create_event_logger(
        service=worker.service_name,
        environment=worker.environment,
        app_version=worker.app_version,
        release_commit_sha=resolved_settings.release_commit_sha,
        level=resolved_settings.log_level,
    )
    try:
        asyncio.run(run_outbox_relay(resolved_settings, event_logger))
    finally:
        operational_metrics.shutdown(
            metrics_configuration.export_timeout_seconds if metrics_configuration else 0
        )


def main(arguments: list[str] | None = None) -> None:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if not values or values == ["worker"]:
        run_worker()
        return
    if values == ["relay"]:
        run_relay()
        return
    raise SystemExit("Usage: python -m app.main [worker|relay]")


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
    main()
