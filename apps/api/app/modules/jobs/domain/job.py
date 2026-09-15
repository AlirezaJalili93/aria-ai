from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
OutboxStatus = Literal["pending", "published", "failed"]

JOB_STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
OUTBOX_STATUSES = frozenset({"pending", "published", "failed"})

_JOB_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class JobValidationError(ValueError):
    """A documented Job or Outbox invariant was violated."""


@dataclass(frozen=True, slots=True)
class NewJob:
    id: UUID
    account_id: UUID | None
    project_id: UUID | None
    job_type: str
    status: JobStatus
    payload_ref: dict[str, object] | None
    attempt_count: int
    max_attempts: int
    idempotency_key: str | None
    correlation_id: UUID
    available_at: datetime

    def __post_init__(self) -> None:
        validate_job_status(self.status)
        validate_attempts(self.attempt_count, self.max_attempts)
        _require_timezone(self.available_at, "available_at")
        if self.project_id is not None and self.account_id is None:
            raise JobValidationError("A project-scoped Job requires account_id")


@dataclass(frozen=True, slots=True)
class Job(NewJob):
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        NewJob.__post_init__(self)
        _require_optional_timezone(self.started_at, "started_at")
        _require_optional_timezone(self.finished_at, "finished_at")
        _require_timezone(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class NewOutboxEvent:
    id: UUID
    account_id: UUID | None
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: dict[str, object]
    status: OutboxStatus
    attempt_count: int
    available_at: datetime

    def __post_init__(self) -> None:
        validate_outbox_status(self.status)
        if self.attempt_count < 0:
            raise JobValidationError("Outbox attempt_count cannot be negative")
        _require_timezone(self.available_at, "available_at")


@dataclass(frozen=True, slots=True)
class OutboxEvent(NewOutboxEvent):
    created_at: datetime
    published_at: datetime | None

    def __post_init__(self) -> None:
        NewOutboxEvent.__post_init__(self)
        _require_timezone(self.created_at, "created_at")
        _require_optional_timezone(self.published_at, "published_at")


def validate_job_status(value: str) -> JobStatus:
    if value not in JOB_STATUSES:
        raise JobValidationError("Unsupported Job status")
    return cast(JobStatus, value)


def validate_outbox_status(value: str) -> OutboxStatus:
    if value not in OUTBOX_STATUSES:
        raise JobValidationError("Unsupported Outbox status")
    return cast(OutboxStatus, value)


def validate_job_transition(current: JobStatus, target: JobStatus) -> None:
    if target not in _JOB_TRANSITIONS[current]:
        raise JobValidationError("Unsupported Job state transition")


def validate_attempts(attempt_count: int, max_attempts: int) -> None:
    if attempt_count < 0:
        raise JobValidationError("Job attempt_count cannot be negative")
    if max_attempts < 1:
        raise JobValidationError("Job max_attempts must be at least one")
    if attempt_count > max_attempts:
        raise JobValidationError("Job attempt_count cannot exceed max_attempts")


def _require_optional_timezone(value: datetime | None, field: str) -> None:
    if value is not None:
        _require_timezone(value, field)


def _require_timezone(value: datetime, field: str) -> None:
    if value.tzinfo is None:
        raise JobValidationError(f"{field} must be timezone-aware")
