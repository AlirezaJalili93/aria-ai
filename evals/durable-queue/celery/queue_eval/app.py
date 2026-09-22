from __future__ import annotations

import os
import re
import time
from urllib.parse import quote

import redis
from celery import Celery

_PROBE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


def _redis_url(database: int) -> str:
    password = quote(os.environ["QUEUE_EVAL_REDIS_PASSWORD"], safe="")
    return f"redis://:{password}@redis:6379/{database}"


visibility_timeout = int(os.environ["QUEUE_EVAL_VISIBILITY_TIMEOUT_SECONDS"])
broker_url = _redis_url(0)
state_url = _redis_url(1)

app = Celery("aria_queue_eval", broker=broker_url)
app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": visibility_timeout},
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_default_queue="aria.queue.evaluation",
)


def state_client() -> redis.Redis:
    return redis.Redis.from_url(state_url, decode_responses=True)


def validate_probe_id(probe_id: str) -> str:
    if not _PROBE_ID_PATTERN.fullmatch(probe_id):
        raise ValueError("probe_id must contain only lowercase letters, digits and hyphens")
    return probe_id


@app.task(name="queue_eval.durable_probe", bind=True, ignore_result=True)
def durable_probe(self: object, probe_id: str, sleep_seconds: float = 0.0) -> None:
    validated_id = validate_probe_id(probe_id)
    state = state_client()
    state.hincrby(f"probe:{validated_id}", "attempts", 1)
    state.hset(f"probe:{validated_id}", mapping={"started": "1"})

    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    if state.set(f"outcome:{validated_id}", "committed", nx=True):
        state.incr(f"business-outcomes:{validated_id}")
    state.hset(f"probe:{validated_id}", mapping={"finished": "1"})
