from __future__ import annotations

import os
import re
import time
from urllib.parse import quote

import dramatiq
import redis
from dramatiq.brokers.redis import RedisBroker

_PROBE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


def _redis_url(database: int) -> str:
    password = quote(os.environ["QUEUE_EVAL_REDIS_PASSWORD"], safe="")
    return f"redis://:{password}@redis:6379/{database}"


broker_url = _redis_url(0)
state_url = _redis_url(1)
heartbeat_timeout_ms = int(os.environ["QUEUE_EVAL_HEARTBEAT_TIMEOUT_MS"])

broker = RedisBroker(
    url=broker_url,
    namespace="aria-dramatiq-eval",
    heartbeat_timeout=heartbeat_timeout_ms,
    maintenance_chance=1_000_000,
)
dramatiq.set_broker(broker)


def state_client() -> redis.Redis:
    return redis.Redis.from_url(state_url, decode_responses=True)


def validate_probe_id(probe_id: str) -> str:
    if not _PROBE_ID_PATTERN.fullmatch(probe_id):
        raise ValueError("probe_id must contain only lowercase letters, digits and hyphens")
    return probe_id


@dramatiq.actor(
    actor_name="queue_eval.durable_probe",
    queue_name="aria_queue_evaluation",
    max_retries=0,
    time_limit=30_000,
)
def durable_probe(probe_id: str, sleep_seconds: float = 0.0) -> None:
    validated_id = validate_probe_id(probe_id)
    state = state_client()
    state.hincrby(f"probe:{validated_id}", "attempts", 1)
    state.hset(f"probe:{validated_id}", mapping={"started": "1"})

    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    if state.set(f"outcome:{validated_id}", "committed", nx=True):
        state.incr(f"business-outcomes:{validated_id}")
    state.hset(f"probe:{validated_id}", mapping={"finished": "1"})
