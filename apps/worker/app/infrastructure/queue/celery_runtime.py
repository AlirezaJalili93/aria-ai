from __future__ import annotations

from dataclasses import dataclass

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import QueueRuntimeConfiguration


def create_celery_app(configuration: QueueRuntimeConfiguration) -> Celery:
    celery_app = Celery(
        "aria-worker",
        broker=configuration.broker_url.get_secret_value(),
        backend=None,
    )
    celery_app.conf.update(
        task_default_queue=configuration.queue_name,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        result_backend=None,
        task_ignore_result=True,
        broker_transport_options={
            "visibility_timeout": configuration.visibility_timeout_seconds,
        },
    )
    return celery_app


@dataclass(frozen=True, slots=True)
class CeleryQueueRuntime:
    celery_app: Celery
    queue_name: str
    concurrency: int
    log_level: str

    def run(self) -> None:
        self.celery_app.worker_main(
            [
                "worker",
                "--loglevel",
                self.log_level,
                "--queues",
                self.queue_name,
                "--concurrency",
                str(self.concurrency),
            ]
        )


def create_celery_queue_runtime(
    configuration: QueueRuntimeConfiguration,
    *,
    log_level: str,
) -> CeleryQueueRuntime:
    return CeleryQueueRuntime(
        celery_app=create_celery_app(configuration),
        queue_name=configuration.queue_name,
        concurrency=configuration.concurrency,
        log_level=log_level,
    )
