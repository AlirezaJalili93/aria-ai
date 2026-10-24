from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
    ContextItemRevision,
    GapDetectionRepositoryError,
    GapDetectionResult,
)
from aria_observability import create_event_logger

from app.application.gap_detection_consumer import (
    GapDetectionConsumer,
    GapDetectionJobInput,
    GapDetectionJobMessage,
    GapDetectionMessageValidationError,
    GapDetectionRuntimePersistenceError,
)
from app.application.gap_detection_runtime import SyntheticGapDetectionCommandFactory


class _Guard:
    def __init__(self, acquisition: str = "acquired") -> None:
        self.acquisition = acquisition
        self.completed: list[object] = []
        self.released: list[object] = []

    async def acquire(self, job_id):
        del job_id
        return self.acquisition

    async def complete(self, job_id) -> None:
        self.completed.append(job_id)

    async def release(self, job_id) -> None:
        self.released.append(job_id)


class _Store:
    def __init__(self, job: GapDetectionJobInput) -> None:
        self.job = job
        self.failed: list[str] = []

    async def prepare(self, message):
        assert message.job_id == self.job.job_id
        return self.job

    async def finalize_failure(self, job, *, error_code: str) -> None:
        assert job == self.job
        self.failed.append(error_code)


class _UseCase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands = []

    async def execute(self, command):
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return GapDetectionResult((), 0, 0, ())


def _job() -> GapDetectionJobInput:
    return GapDetectionJobInput(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        context_version=3,
        context_item_revisions=(
            ContextItemRevision(uuid4(), datetime(2026, 9, 22, tzinfo=UTC)),
        ),
        requirement_revisions=(),
        completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
        critical_rule_pack_version=CRITICAL_GAP_RULE_PACK_VERSION,
        first_attempt=True,
    )


def _consumer(guard, store, use_case, stream):
    return GapDetectionConsumer(
        guard=guard,
        store=store,
        command_factory=SyntheticGapDetectionCommandFactory(),
        use_case=use_case,
        event_logger=create_event_logger(
            service="aria-worker",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=stream,
        ),
    )


def test_consumer_executes_exact_bound_ai03_command_with_empty_requirements() -> None:
    job, guard, use_case = _job(), _Guard(), _UseCase()
    result = asyncio.run(
        _consumer(guard, _Store(job), use_case, StringIO()).execute(
            GapDetectionJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status == "succeeded"
    assert guard.completed == [job.job_id]
    command = use_case.commands[0]
    assert command.context_version == 3
    assert command.context_item_revisions == job.context_item_revisions
    assert command.requirement_revisions == ()
    assert command.task_type == "gap_detection"


@pytest.mark.parametrize("state", ["already_in_progress", "already_completed"])
def test_consumer_suppresses_duplicate_delivery(state: str) -> None:
    job, use_case = _job(), _UseCase()
    result = asyncio.run(
        _consumer(_Guard(state), _Store(job), use_case, StringIO()).execute(
            GapDetectionJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status in {"suppressed", "already_completed"}
    assert use_case.commands == []


def test_persistence_failure_releases_same_job_for_controlled_recovery() -> None:
    job, guard = _job(), _Guard()
    with pytest.raises(GapDetectionRuntimePersistenceError):
        asyncio.run(
            _consumer(
                guard,
                _Store(job),
                _UseCase(GapDetectionRepositoryError("commit_failed")),
                StringIO(),
            ).execute(GapDetectionJobMessage("1", uuid4(), job.job_id))
        )
    assert guard.released == [job.job_id]
    assert guard.completed == []


def test_message_rejects_customer_or_tenant_payload_fields() -> None:
    with pytest.raises(GapDetectionMessageValidationError):
        GapDetectionJobMessage.from_payload(
            {
                "message_version": "1",
                "outbox_event_id": str(uuid4()),
                "job_id": str(uuid4()),
                "requirements": "customer data",
            }
        )
