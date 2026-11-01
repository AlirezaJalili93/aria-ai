from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.scope_generation import (
    ScopeGenerationInputChangedError,
    ScopeGenerationRepositoryError,
    ScopeGenerationResult,
    ScopeInputRevision,
)
from aria_observability import create_event_logger

from app.application.scope_generation_consumer import (
    ExplicitSyntheticScopeProjects,
    ScopeGenerationConsumer,
    ScopeGenerationJobInput,
    ScopeGenerationJobMessage,
    ScopeGenerationMessageValidationError,
    ScopeGenerationRuntimePersistenceError,
)
from app.application.scope_generation_runtime import SyntheticScopeGenerationCommandFactory


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
    def __init__(self, job: ScopeGenerationJobInput) -> None:
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
        return ScopeGenerationResult(
            draft_id=uuid4(), context_version=command.context_version, repair_no=0
        )


def _job() -> ScopeGenerationJobInput:
    revision = ScopeInputRevision(uuid4(), datetime(2026, 9, 27, tzinfo=UTC))
    return ScopeGenerationJobInput(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        context_version=1,
        context_item_revisions=(revision,),
        requirement_revisions=(revision,),
        gap_revisions=(),
        first_attempt=True,
    )


def _consumer(job, guard, store, use_case, *, allowed=True):
    return ScopeGenerationConsumer(
        guard=guard,
        store=store,
        command_factory=SyntheticScopeGenerationCommandFactory(),
        use_case=use_case,
        synthetic_authorizer=ExplicitSyntheticScopeProjects(
            frozenset({(job.account_id, job.project_id)}) if allowed else frozenset()
        ),
        event_logger=create_event_logger(
            service="aria-worker",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        ),
    )


def test_consumer_executes_exact_pinned_synthetic_command() -> None:
    job, guard, use_case = _job(), _Guard(), _UseCase()
    result = asyncio.run(
        _consumer(job, guard, _Store(job), use_case).execute(
            ScopeGenerationJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status == "succeeded"
    assert guard.completed == [job.job_id]
    command = use_case.commands[0]
    assert command.context_item_revisions == job.context_item_revisions
    assert command.requirement_revisions == job.requirement_revisions
    assert command.task_type == "scope_generation"
    assert command.cost_budget == {"paid_calls_allowed": False}


@pytest.mark.parametrize("state", ["already_in_progress", "already_completed"])
def test_duplicate_delivery_is_suppressed(state: str) -> None:
    job, use_case = _job(), _UseCase()
    result = asyncio.run(
        _consumer(job, _Guard(state), _Store(job), use_case).execute(
            ScopeGenerationJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status in {"suppressed", "already_completed"}
    assert use_case.commands == []


def test_input_changed_is_terminal_nonretryable() -> None:
    job, guard = _job(), _Guard()
    store = _Store(job)
    result = asyncio.run(
        _consumer(job, guard, store, _UseCase(ScopeGenerationInputChangedError())).execute(
            ScopeGenerationJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status == "failed"
    assert result.error_code == "SCOPE_GENERATION_INPUT_CHANGED"
    assert store.failed == ["SCOPE_GENERATION_INPUT_CHANGED"]
    assert guard.completed == [job.job_id]


def test_commit_failure_releases_same_job_for_controlled_recovery() -> None:
    job, guard = _job(), _Guard()
    with pytest.raises(ScopeGenerationRuntimePersistenceError):
        asyncio.run(
            _consumer(
                job, guard, _Store(job), _UseCase(ScopeGenerationRepositoryError("commit_failed"))
            ).execute(ScopeGenerationJobMessage("1", uuid4(), job.job_id))
        )
    assert guard.released == [job.job_id]
    assert guard.completed == []


def test_unapproved_synthetic_project_never_invokes_ai() -> None:
    job, use_case = _job(), _UseCase()
    store = _Store(job)
    result = asyncio.run(
        _consumer(job, _Guard(), store, use_case, allowed=False).execute(
            ScopeGenerationJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status == "failed"
    assert use_case.commands == []


def test_message_rejects_customer_payload_fields() -> None:
    with pytest.raises(ScopeGenerationMessageValidationError):
        ScopeGenerationJobMessage.from_payload(
            {
                "message_version": "1",
                "outbox_event_id": str(uuid4()),
                "job_id": str(uuid4()),
                "scope_text": "customer content",
            }
        )
