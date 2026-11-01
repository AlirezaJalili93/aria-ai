from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.requirements_generation import (
    CandidateRequirement,
    CandidateRequirementBatch,
    GenerateRequirementsCommand,
    GenerateRequirementsUseCase,
    RequirementGenerationError,
    RequirementGenerationRepositoryError,
    RequirementRepairPolicy,
    RequirementSnapshotChangedError,
    RequirementSourceReference,
)
from sqlalchemy import inspect, text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.requirements.infrastructure.generation_repository import (
    SqlAlchemyRequirementContextSnapshotReader,
    SqlAlchemyRequirementGenerationUnitOfWorkFactory,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)
API_ROOT = Path(__file__).parents[1]


def _migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _execute(sql: str, parameters: dict[str, object] | None = None) -> None:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


async def _scalar(sql: str, parameters: dict[str, object] | None = None) -> object:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.connect() as connection:
            return (await connection.execute(text(sql), parameters or {})).scalar_one()
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE requirements, context_items, usage_records, outbox_events, jobs, "
            "idempotency_records, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed() -> dict[str, UUID]:
    values = {
        "user": uuid4(),
        "account": uuid4(),
        "project": uuid4(),
        "job": uuid4(),
        "item": uuid4(),
        "source": uuid4(),
        "source_version": uuid4(),
        "correlation": uuid4(),
    }
    await _execute("INSERT INTO profiles (user_id) VALUES (:user)", values)
    await _execute("INSERT INTO accounts (id) VALUES (:account)", values)
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) "
        "VALUES (:project, :account, :user, 'Project', 'landing', 1)",
        values,
    )
    await _execute(
        "INSERT INTO jobs "
        "(id, account_id, project_id, job_type, status, attempt_count, max_attempts, "
        "correlation_id, available_at) VALUES "
        "(:job, :account, :project, 'requirement-generation', 'running', 1, 1, "
        ":correlation, now())",
        values,
    )
    await _execute(
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, created_by) VALUES "
        "(:source, :account, :project, 'text', 'ready', :user)",
        values,
    )
    await _execute(
        "INSERT INTO context_source_versions "
        "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
        "VALUES (:source_version, :account, :project, :source, 1, 'متن ورودی', 'ready')",
        values,
    )
    await _execute(
        "INSERT INTO context_items "
        "(id, account_id, project_id, context_version, item_type, content, source_refs, "
        "status, created_by_type) VALUES "
        "(:item, :account, :project, 1, 'fact', 'محتوای کانتکست', "
        "jsonb_build_array(jsonb_build_object('source_id', CAST(:source_text AS TEXT), "
        "'source_version_id', CAST(:source_version_text AS TEXT))), 'proposed', 'ai')",
        {
            **values,
            "source_text": str(values["source"]),
            "source_version_text": str(values["source_version"]),
        },
    )
    return values


class FakeAI:
    def __init__(self, batch: CandidateRequirementBatch) -> None:
        self.batch = batch
        self.calls = 0

    async def execute_structured(self, **_: object) -> StructuredAIResponse:
        self.calls += 1
        return StructuredAIResponse(
            data=self.batch,
            provider_attempt_id=uuid4(),
            provider="fake",
            model="fake-model",
            provider_request_id="fake-request",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            latency_ms=10,
            retry_no=0,
            workflow_version="workflow-v1",
            prompt_version="prompt-v1",
            estimated_cost=0.01,
            status="success",
        )


class FakeLedger:
    def __init__(self) -> None:
        self.records = []

    async def append(self, record) -> None:
        self.records.append(record)


class PassValidator:
    async def validate(self, **_: object) -> None:
        return None


class NullLogger:
    def emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None:
        del event_name, level, fields


async def _build_service(
    values: dict[str, UUID],
    batch: CandidateRequirementBatch,
    *,
    id_factory=uuid4,
):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    reader = SqlAlchemyRequirementContextSnapshotReader(runtime.session_factory)
    snapshot = await reader.resolve_exact(
        account_id=values["account"],
        project_id=values["project"],
        context_version=1,
    )
    assert snapshot is not None
    ai = FakeAI(batch)
    ledger = FakeLedger()
    service = GenerateRequirementsUseCase(
        snapshot_reader=reader,
        ai_execution=ai,
        usage_ledger=ledger,
        support_validator=PassValidator(),
        unit_of_work_factory=SqlAlchemyRequirementGenerationUnitOfWorkFactory(
            runtime.session_factory
        ),
        event_logger=NullLogger(),
        id_factory=id_factory,
    )
    command_value = GenerateRequirementsCommand(
        account_id=values["account"],
        project_id=values["project"],
        job_id=values["job"],
        correlation_id=values["correlation"],
        context_version=1,
        context_item_revisions=snapshot.revision_vector,
        task_type="opaque-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        repair_prompt_version="repair-v1",
        repair_policy=RequirementRepairPolicy(policy_version="repair-v1", max_repairs=0),
        pricing_version="pricing-v1",
        output_schema={},
        routing_policy={},
        cost_budget={},
        timeout_policy={},
    )
    return runtime, service, command_value, ai, ledger


def _candidate(
    values: dict[str, UUID],
    *,
    title: str = "فرم تماس",
    conflict_group_key: str | None = None,
) -> CandidateRequirement:
    return CandidateRequirement(
        title=title,
        description="شرح Requirement",
        category="functional",
        priority="must",
        source_refs=(
            RequirementSourceReference(values["source"], values["source_version"]),
        ),
        confidence=Decimal("0.8000"),
        unsupported=False,
        duplicate_group_key=None,
        conflict_group_key=conflict_group_key,
    )


def test_generation_schema_extension_and_non_unique_batch_index() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: (
                        {
                            column["name"]: column
                            for column in inspect(sync_connection).get_columns("requirements")
                        },
                        {
                            index["name"]: index
                            for index in inspect(sync_connection).get_indexes("requirements")
                        },
                        {
                            fk["name"]: fk.get("options", {}).get("ondelete")
                            for fk in inspect(sync_connection).get_foreign_keys(
                                "requirements"
                            )
                        },
                    )
                )
        finally:
            await runtime.close()

    columns, indexes, foreign_keys = asyncio.run(inspect_schema())
    assert columns["is_unsupported"]["nullable"] is False
    assert columns["duplicate_group_key"]["nullable"] is True
    assert columns["generation_job_id"]["nullable"] is True
    batch_index = indexes["ix_requirements_account_project_generation_job"]
    assert batch_index["unique"] is False
    assert foreign_keys["fk_requirements_generation_job_id_jobs"] == "RESTRICT"


def test_generation_schema_downgrade_and_reupgrade_recovery() -> None:
    assert TEST_DATABASE_URL is not None
    command.downgrade(_migration_config(), "0011_requirements")

    async def column_names() -> set[str]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: {
                        column["name"]
                        for column in inspect(sync_connection).get_columns("requirements")
                    }
                )
        finally:
            await runtime.close()

    downgraded = asyncio.run(column_names())
    assert "is_unsupported" not in downgraded
    assert "duplicate_group_key" not in downgraded
    assert "generation_job_id" not in downgraded

    command.upgrade(_migration_config(), "head")
    upgraded = asyncio.run(column_names())
    assert {"is_unsupported", "duplicate_group_key", "generation_job_id"} <= upgraded


def test_exact_snapshot_reader_and_atomic_conflict_outbox_persistence() -> None:
    values = asyncio.run(_seed())
    batch = CandidateRequirementBatch(
        (
            _candidate(values, conflict_group_key="opaque-conflict"),
            _candidate(
                values, title="فرم تماس نباشد", conflict_group_key="opaque-conflict"
            ),
        )
    )

    async def scenario():
        runtime, service, command_value, ai, ledger = await _build_service(values, batch)
        try:
            result = await service.execute(command_value)
            return result, ai.calls, len(ledger.records)
        finally:
            await runtime.close()

    result, calls, usage_count = asyncio.run(scenario())
    assert result.persisted_count == 2
    assert result.conflict_count == 1
    assert calls == 1
    assert usage_count == 1
    assert asyncio.run(_scalar("SELECT count(*) FROM requirements")) == 2
    payload = asyncio.run(
        _scalar(
            "SELECT payload FROM outbox_events "
            "WHERE event_type='requirement.conflict_detected'"
        )
    )
    assert payload["project_id"] == str(values["project"])
    assert payload["context_version"] == 1
    assert len(payload["requirement_ids"]) == 2
    assert "conflict_group_key" not in payload


def test_replay_reads_completed_batch_without_second_ai_call() -> None:
    values = asyncio.run(_seed())
    batch = CandidateRequirementBatch((_candidate(values),))

    async def scenario():
        runtime, service, command_value, ai, ledger = await _build_service(values, batch)
        try:
            first = await service.execute(command_value)
            await _execute(
                "UPDATE jobs SET status='succeeded', finished_at=now() WHERE id=:job",
                {"job": values["job"]},
            )
            second = await service.execute(command_value)
            return first, second, ai.calls, len(ledger.records)
        finally:
            await runtime.close()

    first, second, calls, usage_count = asyncio.run(scenario())
    assert first.replayed is False
    assert second.replayed is True
    assert second.requirement_ids == first.requirement_ids
    assert calls == 1
    assert usage_count == 1
    assert asyncio.run(_scalar("SELECT count(*) FROM requirements")) == 1


def test_failed_terminal_job_replays_safe_error_without_ai_or_usage() -> None:
    values = asyncio.run(_seed())
    batch = CandidateRequirementBatch((_candidate(values),))
    asyncio.run(
        _execute(
            "UPDATE jobs SET status='failed', error_code='INSUFFICIENT_CONTEXT', "
            "finished_at=now() WHERE id=:job",
            {"job": values["job"]},
        )
    )

    async def scenario():
        runtime, service, command_value, ai, ledger = await _build_service(values, batch)
        try:
            with pytest.raises(RequirementGenerationError) as raised:
                await service.execute(command_value)
            return raised.value, ai.calls, len(ledger.records)
        finally:
            await runtime.close()

    error, calls, usage_count = asyncio.run(scenario())
    assert error.reason_code == "INSUFFICIENT_CONTEXT"
    assert calls == 0
    assert usage_count == 0
    assert asyncio.run(_scalar("SELECT count(*) FROM requirements")) == 0


def test_snapshot_state_change_after_capture_prevents_all_business_persistence() -> None:
    values = asyncio.run(_seed())
    batch = CandidateRequirementBatch((_candidate(values),))

    async def scenario():
        runtime, service, command_value, _, ledger = await _build_service(values, batch)
        try:
            await _execute(
                "UPDATE context_items SET status='rejected' WHERE id=:item",
                {"item": values["item"]},
            )
            with pytest.raises(RequirementSnapshotChangedError) as raised:
                await service.execute(command_value)
            return raised.value, len(ledger.records)
        finally:
            await runtime.close()

    error, usage_count = asyncio.run(scenario())
    assert getattr(error, "code", None) == "CONTEXT_SNAPSHOT_CHANGED"
    assert usage_count == 0
    assert asyncio.run(_scalar("SELECT count(*) FROM requirements")) == 0
    assert asyncio.run(_scalar("SELECT count(*) FROM outbox_events")) == 0


def test_outbox_constraint_failure_rolls_back_the_complete_requirement_batch() -> None:
    values = asyncio.run(_seed())
    batch = CandidateRequirementBatch(
        (
            _candidate(values, title="A", conflict_group_key="group-a"),
            _candidate(values, title="B", conflict_group_key="group-a"),
            _candidate(values, title="C", conflict_group_key="group-b"),
            _candidate(values, title="D", conflict_group_key="group-b"),
        )
    )
    generated_ids = [uuid4() for _ in range(4)]
    repeated_event_id = uuid4()
    ids = iter([*generated_ids, repeated_event_id, repeated_event_id])

    async def scenario():
        runtime, service, command_value, _, ledger = await _build_service(
            values, batch, id_factory=lambda: next(ids)
        )
        try:
            with pytest.raises(RequirementGenerationRepositoryError):
                await service.execute(command_value)
            return len(ledger.records)
        finally:
            await runtime.close()

    assert asyncio.run(scenario()) == 1
    assert asyncio.run(_scalar("SELECT count(*) FROM requirements")) == 0
    assert asyncio.run(_scalar("SELECT count(*) FROM outbox_events")) == 0
