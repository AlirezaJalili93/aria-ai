from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerBootstrap:
    service_name: str = "aria-worker"
    queue_adapter_configured: bool = False


def bootstrap_worker() -> WorkerBootstrap:
    return WorkerBootstrap()


if __name__ == "__main__":
    worker = bootstrap_worker()
    print(f"{worker.service_name}: bootstrap-ready")

