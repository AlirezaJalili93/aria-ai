from __future__ import annotations

import os
import re
import time
from urllib.parse import quote

import redis
from rq import Queue
from rq.serializers import JSONSerializer

_PROBE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
QUEUE_NAME = "aria_queue_evaluation"


def _redis_url(database: int) -> str:
    password = quote(os.environ["QUEUE_EVAL_REDIS_PASSWORD"], safe="")
    return f"redis://:{password}@redis:6379/{database}"


broker_url = _redis_url(0)
state_url = _redis_url(1)


def broker_client() -> redis.Redis:
    return redis.Redis.from_url(broker_url, decode_responses=False)


def state_client() -> redis.Redis:
    return redis.Redis.from_url(state_url, decode_responses=True)


def queue() -> Queue:
    return Queue(QUEUE_NAME, connection=broker_client(), serializer=JSONSerializer)


def validate_probe_id(probe_id: str) -> str:
    if not _PROBE_ID_PATTERN.fullmatch(probe_id):
        raise ValueError("probe_id must contain only lowercase letters, digits and hyphens")
    return probe_id


def durable_probe(
    probe_id: str,
    sleep_seconds: float = 0.0,
    fail_first_attempt: bool = False,
) -> None:
    validated_id = validate_probe_id(probe_id)
    state = state_client()
    attempts = state.hincrby(f"probe:{validated_id}", "attempts", 1)
    state.hset(f"probe:{validated_id}", mapping={"started": "1"})

    if fail_first_attempt and attempts == 1:
        raise RuntimeError("intentional queue evaluation failure")

    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    if state.set(f"outcome:{validated_id}", "committed", nx=True):
        state.incr(f"business-outcomes:{validated_id}")
    state.hset(f"probe:{validated_id}", mapping={"finished": "1"})
