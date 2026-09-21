from __future__ import annotations

import asyncio
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.context_structuring import (
    ContextRepairPolicy,
    ContextStructuringCommand,
    ContextStructuringRepositoryError,
    ContextStructuringResult,
    ContextStructuringSourceError,
)
from aria_observability import create_event_logger

from app.application.context_structuring_consumer import (
    ContextStructuringConsumer,
    ContextStructuringJobInput,
    ContextStructuringJobMessage,
    ContextStructuringMessageValidationError,
    ContextStructuringRuntimePersistenceError,
)


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
    def __init__(self, job: ContextStructuringJobInput) -> None:
        self.job = job
        self.failed: list[str] = []

    async def prepare(self, message):
        assert message.job_id == self.job.job_id
        return self.job

    async def finalize_failure(self, job, *, error_code: str) -> None:
        assert job == self.job
        self.failed.append(error_code)


class _CommandFactory:
    def build(self, job: ContextStructuringJobInput) -> ContextStructuringCommand:
        return ContextStructuringCommand(
            account_id=job.account_id,
            project_id=job.project_id,
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            task_type="context_structuring",
            workflow_version="synthetic-ai-01-v1",
            prompt_version="synthetic-prompt-v1",
            repair_prompt_version="synthetic-repair-v1",
            repair_policy=ContextRepairPolicy(
                policy_version="synthetic-no-repair-v1",
                max_repairs=0,
            ),
            pricing_version="synthetic-zero-v1",
            output_schema={"synthetic": True},
            routing_policy={"tier": "standard", "synthetic": True},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={"synthetic": True},
        )


class _UseCase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[ContextStructuringCommand] = []

    async def execute(self, command: ContextStructuringCommand) -> ContextStructuringResult:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return ContextStructuringResult(context_version=1, item_count=1)


def _job() -> ContextStructuringJobInput:
    return ContextStructuringJobInput(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        first_attempt=True,
    )


def _consumer(guard: _Guard, store: _Store, use_case: _UseCase, stream: StringIO):
    return ContextStructuringConsumer(
        guard=guard,  # type: ignore[arg-type]
        store=store,
        command_factory=_CommandFactory(),
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


def test_consumer_executes_ai01_and_completes_guard() -> None:
    job = _job()
    guard, store, use_case = _Guard(), _Store(job), _UseCase()
    result = asyncio.run(
        _consumer(guard, store, use_case, StringIO()).execute(
            ContextStructuringJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status == "succeeded"
    assert guard.completed == [job.job_id]
    assert use_case.commands[0].task_type == "context_structuring"


@pytest.mark.parametrize("state", ["already_in_progress", "already_completed"])
def test_consumer_suppresses_duplicate_delivery(state: str) -> None:
    job = _job()
    guard = _Guard(state)
    use_case = _UseCase()
    result = asyncio.run(
        _consumer(guard, _Store(job), use_case, StringIO()).execute(
            ContextStructuringJobMessage("1", uuid4(), job.job_id)
        )
    )
    assert result.status in {"suppressed", "already_completed"}
    assert use_case.commands == []


def test_repository_failure_is_recoverable_and_never_finalizes_success() -> None:
    job = _job()
    guard, store = _Guard(), _Store(job)
    stream = StringIO()
    consumer = _consumer(
        guard,
        store,
        _UseCase(ContextStructuringRepositoryError("context_persistence_failed")),
        stream,
    )

    with pytest.raises(ContextStructuringRuntimePersistenceError):
        asyncio.run(
            consumer.execute(ContextStructuringJobMessage("1", uuid4(), job.job_id))
        )

    assert guard.released == [job.job_id]
    assert guard.completed == []
    assert "CONTEXT_STRUCTURING_PERSISTENCE_UNAVAILABLE" in stream.getvalue()


def test_declared_validation_failure_becomes_terminal_without_content_leakage() -> None:
    job = _job()
    guard, store = _Guard(), _Store(job)
    stream = StringIO()
    result = asyncio.run(
        _consumer(
            guard,
            store,
            _UseCase(ContextStructuringSourceError("ready_source_required")),
            stream,
        ).execute(ContextStructuringJobMessage("1", uuid4(), job.job_id))
    )
    assert result.status == "failed"
    assert store.failed == ["READY_SOURCE_REQUIRED"]
    assert guard.completed == [job.job_id]
    assert "customer text" not in stream.getvalue()


def test_message_requires_exact_identifier_only_envelope() -> None:
    with pytest.raises(ContextStructuringMessageValidationError):
        ContextStructuringJobMessage.from_payload(
            {
                "message_version": "1",
                "outbox_event_id": str(uuid4()),
                "job_id": str(uuid4()),
                "project_id": str(uuid4()),
            }
        )
