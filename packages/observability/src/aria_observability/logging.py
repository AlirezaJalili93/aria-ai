from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from itertools import count
from typing import TextIO
from uuid import UUID

from aria_observability.context import current_trace_context

_LOGGER_SEQUENCE = count()
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_OPTIONAL_FIELDS = {
    "route",
    "task_type",
    "duration_ms",
    "latency_ms",
    "status",
    "error_code",
    "reason_code",
    "provider",
    "model",
    "workflow",
    "attempt",
    "input_tokens",
    "output_tokens",
    "estimated_cost",
    "provider_request_id",
    "exception_type",
    "component",
    "operation",
    "queue_adapter_configured",
    "actor_id",
    "project_id",
}


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_name(value: object) -> str | None:
    if not isinstance(value, str) or _SAFE_NAME.fullmatch(value) is None:
        return None
    return value


def _safe_route(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    route = value.split("?", maxsplit=1)[0]
    if not route.startswith("/") or len(route) > 256 or "\n" in route or "\r" in route:
        return None
    return route


def _safe_duration(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return round(value, 3)


def _safe_non_negative_integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_non_negative_number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return round(value, 6)


def _safe_uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def _safe_status(value: object) -> int | str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    return _safe_name(value)


def _safe_optional_value(field: str, value: object) -> object | None:
    if field == "route":
        return _safe_route(value)
    if field in {"duration_ms", "latency_ms"}:
        return _safe_duration(value)
    if field == "status":
        return _safe_status(value)
    if field == "queue_adapter_configured":
        return value if isinstance(value, bool) else None
    if field in {"actor_id", "project_id"}:
        return _safe_uuid(value)
    if field in {"attempt", "input_tokens", "output_tokens"}:
        return _safe_non_negative_integer(value)
    if field == "estimated_cost":
        return _safe_non_negative_number(value)
    return _safe_name(value)


class StructuredEventLogger:
    def __init__(
        self,
        *,
        service: str,
        environment: str,
        app_version: str,
        release_commit_sha: str | None,
        level: str,
        stream: TextIO | None = None,
    ) -> None:
        if level not in _LEVELS:
            raise ValueError("Unsupported structured log level")
        self._base = {
            "schema_version": "1",
            "service": service,
            "environment": environment,
            "app_version": app_version,
            "release_commit_sha": release_commit_sha,
        }
        logger = logging.getLogger(f"aria.structured.{service}.{next(_LOGGER_SEQUENCE)}")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(_LEVELS[level])
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        self._logger = logger

    def emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None:
        safe_event_name = _safe_name(event_name)
        if safe_event_name is None:
            raise ValueError("event_name must be a safe structured identifier")
        if level not in _LEVELS:
            raise ValueError("Unsupported structured log level")

        context = current_trace_context()
        payload: dict[str, object | None] = {
            "timestamp": _utc_timestamp(),
            "level": level,
            **self._base,
            "event_name": safe_event_name,
            "request_id": context.request_id if context else None,
            "correlation_id": context.correlation_id if context else None,
            "account_id": context.account_id if context else None,
            "project_id": context.project_id if context else None,
            "actor_id": None,
            "job_id": context.job_id if context else None,
            "route": None,
            "task_type": None,
            "duration_ms": None,
            "status": None,
            "error_code": None,
            "provider_request_id": None,
        }
        for field in _OPTIONAL_FIELDS.intersection(fields):
            value = _safe_optional_value(field, fields[field])
            if value is not None:
                payload[field] = value

        self._logger.log(
            _LEVELS[level],
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )


def create_event_logger(
    *,
    service: str,
    environment: str,
    app_version: str,
    release_commit_sha: str | None,
    level: str,
    stream: TextIO | None = None,
) -> StructuredEventLogger:
    return StructuredEventLogger(
        service=service,
        environment=environment,
        app_version=app_version,
        release_commit_sha=release_commit_sha,
        level=level,
        stream=stream,
    )
