from collections.abc import Callable
from dataclasses import dataclass
from threading import Event

from aria_observability import StructuredEventLogger, create_event_logger

from app.core.config import WorkerSettings, load_worker_settings


@dataclass(frozen=True, slots=True)
class WorkerBootstrap:
    service_name: str = "aria-worker"
    queue_adapter_configured: bool = False
    environment: str = "local"
    app_version: str = "0.1.0"


def bootstrap_worker(settings: WorkerSettings | None = None) -> WorkerBootstrap:
    resolved_settings = settings or load_worker_settings()
    return WorkerBootstrap(
        environment=resolved_settings.app_env,
        app_version=resolved_settings.app_version,
    )


def wait_forever() -> None:
    Event().wait()


def run_worker(
    settings: WorkerSettings | None = None,
    wait: Callable[[], None] = wait_forever,
    event_logger: StructuredEventLogger | None = None,
) -> None:
    resolved_settings = settings or load_worker_settings()
    worker = bootstrap_worker(resolved_settings)
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
    wait()


if __name__ == "__main__":
    run_worker()
