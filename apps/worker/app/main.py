from collections.abc import Callable
from dataclasses import dataclass
from threading import Event

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
) -> None:
    worker = bootstrap_worker(settings)
    print(
        f"{worker.service_name}: runtime-started "
        f"environment={worker.environment} version={worker.app_version} "
        f"queue_adapter_configured={str(worker.queue_adapter_configured).lower()}",
        flush=True,
    )
    wait()


if __name__ == "__main__":
    run_worker()
