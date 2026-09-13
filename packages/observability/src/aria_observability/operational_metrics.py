from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Literal, Protocol

MetricValue = int | float
MetricAttributes = Mapping[str, str]
MetricOperation = Literal["counter", "histogram"]

_SAFE_DIMENSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_UUID_VALUE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_RAW_NUMERIC_PATH_SEGMENT = re.compile(r"/(?:[0-9]+)(?:/|$)")
_RAW_UUID_PATH_SEGMENT = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?:/|$)"
)

HTTP_REQUEST_COUNT = "aria.http.server.requests"
HTTP_REQUEST_DURATION = "aria.http.server.request.duration"
WORKER_JOB_COUNT = "aria.worker.jobs"
WORKER_JOB_DURATION = "aria.worker.job.execution.duration"
OUTBOX_PUBLISH_COUNT = "aria.outbox.publish"
AI_PROVIDER_REQUEST_COUNT = "aria.ai.provider.requests"
AI_PROVIDER_DURATION = "aria.ai.provider.duration"
AI_VALIDATION_FAILURE_COUNT = "aria.ai.validation.failures"
AI_COST_TOTAL = "aria.ai.estimated_cost"

_ALLOWED_ATTRIBUTES: dict[str, frozenset[str]] = {
    HTTP_REQUEST_COUNT: frozenset({"route", "method", "status_class"}),
    HTTP_REQUEST_DURATION: frozenset({"route", "method", "status_class"}),
    WORKER_JOB_COUNT: frozenset({"job_type", "status"}),
    WORKER_JOB_DURATION: frozenset({"job_type", "status"}),
    OUTBOX_PUBLISH_COUNT: frozenset({"status"}),
    AI_PROVIDER_REQUEST_COUNT: frozenset(
        {"workflow", "provider", "model", "status"}
    ),
    AI_PROVIDER_DURATION: frozenset({"workflow", "provider", "model", "status"}),
    AI_VALIDATION_FAILURE_COUNT: frozenset({"workflow", "validation_kind"}),
    AI_COST_TOTAL: frozenset({"task_type", "currency"}),
}
_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_ALLOWED_HTTP_STATUS_CLASSES = frozenset({"1xx", "2xx", "3xx", "4xx", "5xx"})
_ALLOWED_JOB_STATUSES = frozenset({"succeeded", "failed"})
_ALLOWED_OUTBOX_STATUSES = frozenset({"succeeded", "failed"})
_ALLOWED_AI_STATUSES = frozenset({"success", "failed", "partial"})
_ALLOWED_VALIDATION_KINDS = frozenset({"schema", "business"})
_STATUS_VALUES_BY_INSTRUMENT = {
    WORKER_JOB_COUNT: _ALLOWED_JOB_STATUSES,
    WORKER_JOB_DURATION: _ALLOWED_JOB_STATUSES,
    OUTBOX_PUBLISH_COUNT: _ALLOWED_OUTBOX_STATUSES,
    AI_PROVIDER_REQUEST_COUNT: _ALLOWED_AI_STATUSES,
    AI_PROVIDER_DURATION: _ALLOWED_AI_STATUSES,
}
_FORBIDDEN_ATTRIBUTES = frozenset(
    {
        "account_id",
        "project_id",
        "job_id",
        "request_id",
        "correlation_id",
        "source_id",
        "requirement_id",
        "gap_id",
        "scope_version_id",
        "email",
        "title",
        "filename",
        "error_message",
        "exception_message",
        "prompt",
        "response",
        "content",
    }
)


class MetricBackend(Protocol):
    """Infrastructure-only backend used behind the bounded metrics dispatcher."""

    def add_counter(
        self, name: str, value: MetricValue, attributes: MetricAttributes
    ) -> None: ...

    def record_histogram(
        self, name: str, value: MetricValue, attributes: MetricAttributes
    ) -> None: ...

    def shutdown(self, timeout_seconds: float) -> None: ...


class OperationalMetrics(Protocol):
    """Provider-neutral operational instrumentation boundary."""

    def record_http_request(
        self, *, route: str, method: str, status_code: int, duration_ms: float
    ) -> None: ...

    def record_worker_job(
        self, *, job_type: str, status: str, duration_ms: float
    ) -> None: ...

    def record_outbox_publish(self, *, status: str) -> None: ...

    def record_ai_usage(
        self,
        *,
        workflow: str,
        provider: str,
        model: str,
        status: str,
        latency_ms: float,
        task_type: str,
        estimated_cost: float,
        currency: str,
    ) -> None: ...

    def record_ai_validation_failure(
        self, *, workflow: str, validation_kind: str
    ) -> None: ...

    def shutdown(self, timeout_seconds: float) -> None: ...


class NoOpOperationalMetrics:
    def record_http_request(
        self, *, route: str, method: str, status_code: int, duration_ms: float
    ) -> None:
        del route, method, status_code, duration_ms

    def record_worker_job(self, *, job_type: str, status: str, duration_ms: float) -> None:
        del job_type, status, duration_ms

    def record_outbox_publish(self, *, status: str) -> None:
        del status

    def record_ai_usage(
        self,
        *,
        workflow: str,
        provider: str,
        model: str,
        status: str,
        latency_ms: float,
        task_type: str,
        estimated_cost: float,
        currency: str,
    ) -> None:
        del (
            workflow,
            provider,
            model,
            status,
            latency_ms,
            task_type,
            estimated_cost,
            currency,
        )

    def record_ai_validation_failure(self, *, workflow: str, validation_kind: str) -> None:
        del workflow, validation_kind

    def shutdown(self, timeout_seconds: float) -> None:
        del timeout_seconds


@dataclass(frozen=True, slots=True)
class MetricAttributePolicy:
    """Reject unknown keys, raw paths, identifiers and unapproved model values."""

    allowed_models: frozenset[str] = frozenset()

    def sanitize(
        self, instrument: str, attributes: Mapping[str, object]
    ) -> dict[str, str] | None:
        allowed = _ALLOWED_ATTRIBUTES.get(instrument)
        if allowed is None or set(attributes) != set(allowed):
            return None
        if _FORBIDDEN_ATTRIBUTES.intersection(attributes):
            return None

        sanitized: dict[str, str] = {}
        for key, raw_value in attributes.items():
            if not isinstance(raw_value, str):
                return None
            value = raw_value.strip()
            if not value or _UUID_VALUE.fullmatch(value):
                return None
            if key == "route":
                if not _safe_route_template(value):
                    return None
            elif key == "method":
                if value not in _ALLOWED_METHODS:
                    return None
            elif key == "status_class":
                if value not in _ALLOWED_HTTP_STATUS_CLASSES:
                    return None
            elif key == "validation_kind":
                if value not in _ALLOWED_VALIDATION_KINDS:
                    return None
            elif key == "status":
                if value not in _STATUS_VALUES_BY_INSTRUMENT.get(
                    instrument, frozenset()
                ):
                    return None
            elif key == "model":
                if value not in self.allowed_models:
                    return None
            elif key == "currency":
                if not re.fullmatch(r"[A-Z]{3}", value):
                    return None
            elif _SAFE_DIMENSION.fullmatch(value) is None:
                return None
            sanitized[key] = value
        return sanitized


@dataclass(frozen=True, slots=True)
class _MetricRecord:
    operation: MetricOperation
    instrument: str
    value: MetricValue
    attributes: Mapping[str, str]


class BufferedOperationalMetrics:
    """Non-blocking, fail-open metrics facade with a bounded in-process queue."""

    def __init__(
        self,
        backend: MetricBackend,
        *,
        queue_capacity: int,
        allowed_models: frozenset[str] = frozenset(),
    ) -> None:
        if isinstance(queue_capacity, bool) or queue_capacity < 1:
            raise ValueError("queue_capacity must be a positive integer")
        self._backend = backend
        self._policy = MetricAttributePolicy(allowed_models=allowed_models)
        self._queue: Queue[_MetricRecord] = Queue(maxsize=queue_capacity)
        self._stop = Event()
        self._thread = Thread(target=self._run, name="aria-operational-metrics", daemon=True)
        self._thread.start()
        self._dropped_count = 0

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    def record_http_request(
        self, *, route: str, method: str, status_code: int, duration_ms: float
    ) -> None:
        if (
            isinstance(status_code, bool)
            or not isinstance(status_code, int)
            or not 100 <= status_code <= 599
        ):
            return
        status_class = f"{status_code // 100}xx"
        attributes = {"route": route, "method": method.upper(), "status_class": status_class}
        self._enqueue("counter", HTTP_REQUEST_COUNT, 1, attributes)
        self._enqueue("histogram", HTTP_REQUEST_DURATION, duration_ms, attributes)

    def record_worker_job(self, *, job_type: str, status: str, duration_ms: float) -> None:
        attributes = {"job_type": job_type, "status": status}
        self._enqueue("counter", WORKER_JOB_COUNT, 1, attributes)
        self._enqueue("histogram", WORKER_JOB_DURATION, duration_ms, attributes)

    def record_outbox_publish(self, *, status: str) -> None:
        self._enqueue("counter", OUTBOX_PUBLISH_COUNT, 1, {"status": status})

    def record_ai_usage(
        self,
        *,
        workflow: str,
        provider: str,
        model: str,
        status: str,
        latency_ms: float,
        task_type: str,
        estimated_cost: float,
        currency: str,
    ) -> None:
        attributes = {
            "workflow": workflow,
            "provider": provider,
            "model": model,
            "status": status,
        }
        self._enqueue("counter", AI_PROVIDER_REQUEST_COUNT, 1, attributes)
        self._enqueue("histogram", AI_PROVIDER_DURATION, latency_ms, attributes)
        self._enqueue(
            "counter",
            AI_COST_TOTAL,
            estimated_cost,
            {"task_type": task_type, "currency": currency},
        )

    def record_ai_validation_failure(
        self, *, workflow: str, validation_kind: str
    ) -> None:
        self._enqueue(
            "counter",
            AI_VALIDATION_FAILURE_COUNT,
            1,
            {"workflow": workflow, "validation_kind": validation_kind},
        )

    def shutdown(self, timeout_seconds: float) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds < 0:
            return
        self._stop.set()
        self._thread.join(timeout=timeout_seconds)

    def _enqueue(
        self,
        operation: MetricOperation,
        instrument: str,
        value: MetricValue,
        attributes: Mapping[str, object],
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return
        sanitized = self._policy.sanitize(instrument, attributes)
        if sanitized is None:
            self._dropped_count += 1
            return
        try:
            self._queue.put_nowait(
                _MetricRecord(
                    operation=operation,
                    instrument=instrument,
                    value=value,
                    attributes=sanitized,
                )
            )
        except Full:
            self._dropped_count += 1

    def _run(self) -> None:
        try:
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    record = self._queue.get(timeout=0.05)
                except Empty:
                    continue
                try:
                    if record.operation == "counter":
                        self._backend.add_counter(
                            record.instrument, record.value, record.attributes
                        )
                    else:
                        self._backend.record_histogram(
                            record.instrument, record.value, record.attributes
                        )
                except Exception:  # noqa: BLE001 -- telemetry must be fail-open
                    self._dropped_count += 1
                finally:
                    self._queue.task_done()
        finally:
            with suppress(Exception):
                self._backend.shutdown(0)


def _safe_route_template(value: str) -> bool:
    return (
        value.startswith("/")
        and len(value) <= 256
        and "?" not in value
        and "#" not in value
        and "\n" not in value
        and "\r" not in value
        and _RAW_UUID_PATH_SEGMENT.search(value) is None
        and _RAW_NUMERIC_PATH_SEGMENT.search(value) is None
    )
