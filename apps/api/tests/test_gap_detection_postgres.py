from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_V1,
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
    CandidateGap,
    CandidateGapBatch,
    ChecklistItemRuleSignal,
    CriticalGapRuleEvaluation,
    DetectGapsCommand,
    DetectGapsUseCase,
    GapDetectionRepositoryError,
    GapRepairPolicy,
    GapSourceReference,
    GapWrite,
    VersionedCriticalGapRuleEvaluator,
)
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.gaps.infrastructure.detection_repository import (
    SqlAlchemyGapDetectionSnapshotReader,
    SqlAlchemyGapDetectionUnitOfWorkFactory,
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
            "TRUNCATE gap_requirement_links, gaps, requirements, context_items, "
            "usage_records, outbox_events, jobs, idempotency_records, "
            "context_source_versions, context_sources, project_create_requests, "
            "projects, account_memberships, profiles, accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed() -> dict[str, UUID]:
    values = {
        "user": uuid4(),
        "account": uuid4(),
        "project": uuid4(),
        "job": uuid4(),
        "context_item": uuid4(),
        "requirement": uuid4(),
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
        "(id, account_id, project_id, job_type, status, payload_ref, attempt_count, "
        "max_attempts, correlation_id, available_at) VALUES "
        "(:job, :account, :project, 'gap-detection', 'running', "
        "jsonb_build_object('snapshot_ref', 'stable'), 1, 1, :correlation, now())",
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
    refs = json.dumps(
        [
            {
                "source_id": str(values["source"]),
                "source_version_id": str(values["source_version"]),
            }
        ]
    )
    await _execute(
        "INSERT INTO context_items "
        "(id, account_id, project_id, context_version, item_type, content, source_refs, "
        "status, created_by_type) VALUES "
        "(:context_item, :account, :project, 1, 'fact', 'محتوای کانتکست', "
        "CAST(:refs AS jsonb), 'confirmed', 'ai')",
        {**values, "refs": refs},
    )
    await _execute(
        "INSERT INTO requirements "
        "(id, account_id, project_id, context_version, category, title, description, "
        "priority, status, source_refs, created_by_type) VALUES "
        "(:requirement, :account, :project, 1, 'functional', 'عنوان', 'شرح', "
        "'must', 'confirmed', CAST(:refs AS jsonb), 'ai')",
        {**values, "refs": refs},
    )
    return values


class FakeAI:
    def __init__(self, batch: CandidateGapBatch) -> None:
        self.batch = batch
        self.calls = 0

    async def execute_structured(self, **_: object) -> StructuredAIResponse:
        self.calls += 1
        return StructuredAIResponse(
            data=self.batch,
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


class NoCriticalRules:
    async def evaluate(self, **_: object) -> CriticalGapRuleEvaluation:
        return CriticalGapRuleEvaluation(())


class NullLogger:
    def emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None:
        del event_name, level, fields


async def _service(
    values: dict[str, UUID],
    batch: CandidateGapBatch,
    critical_rules=None,
):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    reader = SqlAlchemyGapDetectionSnapshotReader(runtime.session_factory)
    snapshot = await reader.resolve_exact(
        account_id=values["account"],
        project_id=values["project"],
        context_version=1,
        completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
    )
    assert snapshot is not None
    ai, ledger = FakeAI(batch), FakeLedger()
    service = DetectGapsUseCase(
        snapshot_reader=reader,
        ai_execution=ai,
        usage_ledger=ledger,
        critical_rule_evaluator=critical_rules or NoCriticalRules(),
        unit_of_work_factory=SqlAlchemyGapDetectionUnitOfWorkFactory(runtime.session_factory),
        event_logger=NullLogger(),
        wall_clock=lambda: datetime(2026, 9, 9, tzinfo=UTC),
    )
    command_value = DetectGapsCommand(
        account_id=values["account"],
        project_id=values["project"],
        job_id=values["job"],
        correlation_id=values["correlation"],
        context_version=1,
        context_item_revisions=snapshot.context_item_revisions,
        requirement_revisions=snapshot.requirement_revisions,
        completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
        critical_rule_pack_version=CRITICAL_GAP_RULE_PACK_VERSION,
        task_type="opaque-gap-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        repair_prompt_version="repair-v1",
        repair_policy=GapRepairPolicy(policy_version="repair-v1", max_repairs=0),
        pricing_version="pricing-v1",
        output_schema={},
        routing_policy={},
        cost_budget={},
        timeout_policy={},
    )
    return runtime, service, command_value, ai, ledger


def _candidate(values: dict[str, UUID]) -> CandidateGap:
    return CandidateGap(
        gap_type="ambiguity",
        severity="critical",
        explanation="ابهام شناسایی شد",
        source_refs=(GapSourceReference(values["source"], values["source_version"]),),
        affected_requirement_ids=(values["requirement"],),
        suggested_resolution_type="clarify_ambiguity",
    )


def test_j02_schema_is_private_tenant_safe_and_normalized() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync: (
                        {column["name"] for column in inspect(sync).get_columns("gaps")},
                        {
                            column["name"]
                            for column in inspect(sync).get_columns("gap_requirement_links")
                        },
                        {
                            fk["name"]: fk.get("options", {}).get("ondelete")
                            for fk in inspect(sync).get_foreign_keys("gap_requirement_links")
                        },
                    )
                )
        finally:
            await runtime.close()

    gap_columns, link_columns, link_fks = asyncio.run(inspect_schema())
    assert {"explanation", "suggested_resolution_type", "generation_job_id"} <= gap_columns
    assert link_columns == {
        "account_id",
        "project_id",
        "gap_id",
        "requirement_id",
        "created_at",
    }
    assert link_fks == {
        "fk_gap_requirement_links_gap_tenant": "RESTRICT",
        "fk_gap_requirement_links_requirement_tenant": "RESTRICT",
    }
    assert (
        asyncio.run(
            _scalar(
                "SELECT relrowsecurity FROM pg_catalog.pg_class "
                "WHERE oid='public.gap_requirement_links'::regclass"
            )
        )
        is True
    )
    assert (
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='public' AND table_name='gap_requirement_links' "
                "AND grantee IN ('anon','authenticated')"
            )
        )
        == 0
    )


def test_nonempty_detection_persists_gap_link_job_metadata_and_replays() -> None:
    async def scenario() -> None:
        values = await _seed()
        runtime, service, command_value, ai, ledger = await _service(
            values, CandidateGapBatch((_candidate(values),))
        )
        try:
            result = await service.execute(command_value)
            assert result.gap_count == 1
            row = await _scalar(
                "SELECT jsonb_build_object('gap_count', payload_ref->'gap_count', "
                "'critical_candidate_count', payload_ref->'critical_candidate_count', "
                "'rule_generated_gap_count', payload_ref->'rule_generated_gap_count', "
                "'critical_gap_count', payload_ref->'critical_gap_count', "
                "'completion_checklist_version', "
                "payload_ref->'completion_checklist_version', "
                "'critical_rule_pack_version', payload_ref->'critical_rule_pack_version', "
                "'snapshot_ref', payload_ref->'snapshot_ref', 'status', status) "
                "FROM jobs WHERE id=:job",
                values,
            )
            assert row == {
                "gap_count": 1,
                "critical_candidate_count": 1,
                "rule_generated_gap_count": 0,
                "critical_gap_count": 0,
                "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
                "critical_rule_pack_version": CRITICAL_GAP_RULE_PACK_VERSION,
                "snapshot_ref": "stable",
                "status": "succeeded",
            }
            assert await _scalar("SELECT count(*) FROM gap_requirement_links") == 1

            replay = await service.execute(command_value)
            assert replay.replayed is True and replay.gap_ids == result.gap_ids
            assert replay.critical_candidate_count == 1
            assert ai.calls == len(ledger.records) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_empty_detection_commits_zero_metadata_and_replays_without_ai() -> None:
    async def scenario() -> None:
        values = await _seed()
        runtime, service, command_value, ai, ledger = await _service(values, CandidateGapBatch(()))
        try:
            result = await service.execute(command_value)
            replay = await service.execute(command_value)
            assert result.gap_count == replay.gap_count == 0
            assert replay.replayed is True
            assert await _scalar("SELECT payload_ref->>'gap_count' FROM jobs") == "0"
            assert await _scalar("SELECT count(*) FROM gaps") == 0
            assert ai.calls == len(ledger.records) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_rule_generated_critical_gap_and_pinned_policy_metadata_are_atomic() -> None:
    async def scenario() -> None:
        values = await _seed()
        items = COMPLETION_CHECKLIST_V1.items_for("landing")
        assert items is not None
        signals = tuple(
            ChecklistItemRuleSignal(
                signal_type="checklist_item",
                signal_origin="ai_candidate",
                checklist_item_id=item.item_id,
                state="missing" if item.item_id == "project.objective" else "present",
                supporting_context_item_ids=(
                    ()
                    if item.item_id == "project.objective"
                    else (values["context_item"],)
                ),
            )
            for item in items
        )
        runtime, service, command_value, ai, ledger = await _service(
            values,
            CandidateGapBatch(items=(), rule_signals=signals),
            VersionedCriticalGapRuleEvaluator(),
        )
        try:
            result = await service.execute(command_value)
            assert result.gap_count == 1
            assert result.rule_generated_gap_count == 1
            assert result.critical_gap_count == 1
            assert await _scalar("SELECT severity FROM gaps") == "critical"
            metadata = await _scalar(
                "SELECT payload_ref FROM jobs WHERE id=:job", values
            )
            assert metadata["completion_checklist_version"] == COMPLETION_CHECKLIST_VERSION
            assert metadata["critical_rule_pack_version"] == CRITICAL_GAP_RULE_PACK_VERSION
            assert metadata["rule_generated_gap_count"] == 1
            assert metadata["critical_gap_count"] == 1
            replay = await service.execute(command_value)
            assert replay.replayed is True
            assert replay.rule_generated_gap_count == 1
            assert replay.critical_gap_count == 1
            assert ai.calls == len(ledger.records) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_replay_rejects_corrupt_critical_count_metadata() -> None:
    async def scenario() -> None:
        values = await _seed()
        items = COMPLETION_CHECKLIST_V1.items_for("landing")
        assert items is not None
        signals = tuple(
            ChecklistItemRuleSignal(
                signal_type="checklist_item",
                signal_origin="ai_candidate",
                checklist_item_id=item.item_id,
                state="missing" if item.item_id == "project.objective" else "present",
                supporting_context_item_ids=(
                    ()
                    if item.item_id == "project.objective"
                    else (values["context_item"],)
                ),
            )
            for item in items
        )
        runtime, service, command_value, ai, ledger = await _service(
            values,
            CandidateGapBatch(items=(), rule_signals=signals),
            VersionedCriticalGapRuleEvaluator(),
        )
        try:
            await service.execute(command_value)
            await _execute(
                "UPDATE jobs SET payload_ref=jsonb_set(payload_ref, "
                "'{critical_gap_count}', '0'::jsonb) WHERE id=:job",
                values,
            )
            with pytest.raises(
                GapDetectionRepositoryError, match="invalid_gap_replay_metadata"
            ):
                await service.execute(command_value)
            assert ai.calls == len(ledger.records) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_concurrent_delivery_commits_one_batch_and_serves_one_replay() -> None:
    async def scenario() -> None:
        values = await _seed()
        runtime_a, service_a, command_a, ai_a, ledger_a = await _service(
            values, CandidateGapBatch((_candidate(values),))
        )
        runtime_b, service_b, command_b, ai_b, ledger_b = await _service(
            values, CandidateGapBatch((_candidate(values),))
        )
        try:
            results = await asyncio.gather(
                service_a.execute(command_a), service_b.execute(command_b)
            )
            assert sum(result.replayed for result in results) == 1
            assert results[0].gap_ids == results[1].gap_ids
            assert await _scalar("SELECT count(*) FROM gaps") == 1
            assert await _scalar("SELECT count(*) FROM gap_requirement_links") == 1
            assert ai_a.calls + ai_b.calls in {1, 2}
            assert len(ledger_a.records) + len(ledger_b.records) == ai_a.calls + ai_b.calls
        finally:
            await runtime_a.close()
            await runtime_b.close()

    asyncio.run(scenario())


def test_database_rejects_link_to_requirement_from_another_snapshot() -> None:
    values = asyncio.run(_seed())
    other_requirement = uuid4()
    asyncio.run(
        _execute(
            "UPDATE projects SET current_context_version=2 WHERE id=:project",
            values,
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO requirements "
            "(id, account_id, project_id, context_version, category, title, description, "
            "priority, status, created_by_type) VALUES "
            "(:other, :account, :project, 2, 'functional', 'Other', 'Other', "
            "'must', 'draft', 'ai')",
            {**values, "other": other_requirement},
        )
    )
    gap_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO gaps "
            "(id, account_id, project_id, context_version, gap_type, severity, "
            "explanation, suggested_resolution_type, generation_job_id) VALUES "
            "(:gap, :account, :project, 1, 'ambiguity', 'high', 'why', "
            "'clarify_ambiguity', :job)",
            {**values, "gap": gap_id},
        )
    )
    with pytest.raises(IntegrityError, match="same Context snapshot"):
        asyncio.run(
            _execute(
                "INSERT INTO gap_requirement_links "
                "(account_id, project_id, gap_id, requirement_id) VALUES "
                "(:account, :project, :gap, :other)",
                {**values, "gap": gap_id, "other": other_requirement},
            )
        )


def test_database_rejects_cross_tenant_generation_job() -> None:
    values = asyncio.run(_seed())
    other = asyncio.run(_seed())
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                "INSERT INTO gaps "
                "(id, account_id, project_id, context_version, gap_type, severity, "
                "explanation, suggested_resolution_type, generation_job_id) VALUES "
                "(:gap, :account, :project, 1, 'ambiguity', 'high', 'why', "
                "'clarify_ambiguity', :other_job)",
                {**values, "gap": uuid4(), "other_job": other["job"]},
            )
        )


def test_database_rejects_unapproved_resolution_vocabulary() -> None:
    values = asyncio.run(_seed())
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                "INSERT INTO gaps "
                "(id, account_id, project_id, context_version, gap_type, severity, "
                "explanation, suggested_resolution_type, generation_job_id) VALUES "
                "(:gap, :account, :project, 1, 'ambiguity', 'high', 'why', "
                "'invented_resolution', :job)",
                {**values, "gap": uuid4()},
            )
        )


def test_snapshot_reader_rejects_corrupt_or_nonready_persisted_provenance() -> None:
    values = asyncio.run(_seed())
    invalid_version = uuid4()
    asyncio.run(
        _execute(
            "UPDATE context_items SET source_refs=jsonb_build_array(jsonb_build_object("
            "'source_id', CAST(:source_text AS text), "
            "'source_version_id', CAST(:invalid_text AS text))) WHERE id=:context_item",
            {
                **values,
                "source_text": str(values["source"]),
                "invalid_text": str(invalid_version),
            },
        )
    )

    async def read() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            reader = SqlAlchemyGapDetectionSnapshotReader(runtime.session_factory)
            await reader.resolve_exact(
                account_id=values["account"],
                project_id=values["project"],
                context_version=1,
                completion_checklist_version="checklist-v1",
            )
        finally:
            await runtime.close()

    with pytest.raises(GapDetectionRepositoryError, match="invalid_gap_snapshot_provenance"):
        asyncio.run(read())


def test_repository_failure_rolls_back_gap_and_link_together() -> None:
    values = asyncio.run(_seed())
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    factory = SqlAlchemyGapDetectionUnitOfWorkFactory(runtime.session_factory)
    try:
        invalid_write = GapWrite(
            id=uuid4(),
            account_id=values["account"],
            project_id=values["project"],
            context_version=1,
            gap_type="ambiguity",
            severity="high",
            explanation="why",
            source_refs=(),
            suggested_resolution_type="clarify_ambiguity",
            generation_job_id=values["job"],
            affected_requirement_ids=(uuid4(),),
        )

        async def attempt() -> None:
            async with factory() as unit_of_work:
                await unit_of_work.repository.add_batch((invalid_write,))
                await unit_of_work.commit()

        with pytest.raises(GapDetectionRepositoryError):
            asyncio.run(attempt())
        assert asyncio.run(_scalar("SELECT count(*) FROM gaps")) == 0
        assert asyncio.run(_scalar("SELECT count(*) FROM gap_requirement_links")) == 0
    finally:
        asyncio.run(runtime.close())
