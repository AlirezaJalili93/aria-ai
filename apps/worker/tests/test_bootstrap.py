from app.main import bootstrap_worker


def test_bootstrap_worker_remains_queue_neutral() -> None:
    worker = bootstrap_worker()

    assert worker.service_name == "aria-worker"
    assert worker.queue_adapter_configured is False
