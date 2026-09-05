from unittest.mock import Mock

from pydantic import SecretStr

from app.core.config import QueueRuntimeConfiguration
from app.infrastructure.queue.celery_runtime import (
    CeleryQueueRuntime,
    create_celery_app,
)


def configuration() -> QueueRuntimeConfiguration:
    return QueueRuntimeConfiguration(
        broker_url=SecretStr("redis://queue.test:6379/0"),
        queue_name="aria-test-jobs",
        visibility_timeout_seconds=60,
        concurrency=2,
    )


def test_celery_app_uses_approved_transport_configuration() -> None:
    celery_app = create_celery_app(configuration())

    assert celery_app.conf.task_default_queue == "aria-test-jobs"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.result_backend is None
    assert celery_app.conf.task_ignore_result is True
    assert celery_app.conf.broker_transport_options == {"visibility_timeout": 60}
    assert celery_app.conf.task_soft_time_limit is None
    assert celery_app.conf.task_time_limit is None


def test_celery_runtime_passes_only_explicit_process_values() -> None:
    celery_app = Mock()
    runtime = CeleryQueueRuntime(
        celery_app=celery_app,  # type: ignore[arg-type]
        queue_name="aria-test-jobs",
        concurrency=2,
        log_level="INFO",
    )

    runtime.run()

    celery_app.worker_main.assert_called_once_with(
        [
            "worker",
            "--loglevel",
            "INFO",
            "--queues",
            "aria-test-jobs",
            "--concurrency",
            "2",
        ]
    )
