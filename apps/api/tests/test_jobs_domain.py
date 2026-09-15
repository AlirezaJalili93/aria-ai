from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.jobs.domain.job import (
    JobValidationError,
    NewJob,
    NewOutboxEvent,
    validate_job_transition,
)


def _job(**changes: object) -> NewJob:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "job_type": "context_parse",
        "status": "queued",
        "payload_ref": {"source_id": str(uuid4())},
        "attempt_count": 0,
        "max_attempts": 3,
        "idempotency_key": "key",
        "correlation_id": uuid4(),
        "available_at": datetime.now(UTC),
    }
    values.update(changes)
    return NewJob(**values)  # type: ignore[arg-type]


def test_job_vocabulary_attempts_and_project_tenant_are_enforced() -> None:
    assert _job().status == "queued"
    with pytest.raises(JobValidationError):
        _job(status="unknown")
    with pytest.raises(JobValidationError):
        _job(attempt_count=-1)
    with pytest.raises(JobValidationError):
        _job(max_attempts=0)
    with pytest.raises(JobValidationError):
        _job(attempt_count=4, max_attempts=3)
    with pytest.raises(JobValidationError):
        _job(account_id=None)


def test_job_state_machine_matches_the_approved_one_way_flow() -> None:
    for current, target in (
        ("queued", "running"),
        ("queued", "cancelled"),
        ("running", "succeeded"),
        ("running", "failed"),
        ("running", "cancelled"),
    ):
        validate_job_transition(current, target)  # type: ignore[arg-type]

    for current, target in (
        ("queued", "succeeded"),
        ("succeeded", "running"),
        ("failed", "queued"),
        ("cancelled", "running"),
    ):
        with pytest.raises(JobValidationError):
            validate_job_transition(current, target)  # type: ignore[arg-type]


def test_outbox_vocabulary_and_attempts_are_enforced() -> None:
    now = datetime.now(UTC)
    event = NewOutboxEvent(
        id=uuid4(),
        account_id=uuid4(),
        aggregate_type="context_source",
        aggregate_id=uuid4(),
        event_type="context_added.v1",
        payload={"payloadVersion": "1"},
        status="pending",
        attempt_count=0,
        available_at=now,
    )
    assert event.status == "pending"
    with pytest.raises(JobValidationError):
        NewOutboxEvent(
            id=uuid4(),
            account_id=None,
            aggregate_type="system",
            aggregate_id=uuid4(),
            event_type="context_added.v1",
            payload={},
            status="invalid",  # type: ignore[arg-type]
            attempt_count=0,
            available_at=now,
        )
    with pytest.raises(JobValidationError):
        NewOutboxEvent(
            id=uuid4(),
            account_id=None,
            aggregate_type="system",
            aggregate_id=uuid4(),
            event_type="context_added.v1",
            payload={},
            status="pending",
            attempt_count=-1,
            available_at=now,
        )
