from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
    DetectGapsUseCase,
    GapDetectionRepositoryError,
    GapDetectionUnitOfWork,
    VersionedCriticalGapRuleEvaluator,
)
from aria_observability import create_event_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.gap_detection_consumer import (
    GapDetectionConsumer,
    GapDetectionJobMessage,
    GapDetectionRuntimePersistenceError,
)
from app.application.gap_detection_runtime import SyntheticGapDetectionCommandFactory
from app.infrastructure.ai.synthetic_gap_detection import SyntheticGapDetectionAI
from app.infrastructure.db.gap_detection_runtime import (
    PostgresGapDetectionSnapshotReader,
    PostgresGapDetectionUnitOfWorkFactory,
    SqlAlchemyGapDetectionJobStore,
)
from app.infrastructure.db.txt_parser_runtime import PostgresJobExecutionGuard

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


@dataclass(frozen=True, slots=True)
class _Fixture:
    user_id: UUID
    account_id: UUID
    project_id: UUID
    context_item_id: UUID
    job_id: UUID
    outbox_event_id: UUID
    correlation_id: UUID


class _UsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class _FailCommitUnitOfWork:
    def __init__(self, inner: GapDetectionUnitOfWork) -> None:
        self._inner = inner

    @property
    def repository(self):
        return self._inner.repository

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._inner.__aexit__(exc_type, exc, traceback)

    async def commit(self) -> None:
        raise GapDetectionRepositoryError("synthetic_commit_failure")


class _FailCommitFactory:
    def __init__(self, inner: PostgresGapDetectionUnitOfWorkFactory) -> None:
        self._inner = inner

    def __call__(self) -> _FailCommitUnitOfWork:
        return _FailCommitUnitOfWork(self._inner())


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    if TEST_DATABASE_URL.startswith("postgresql+asyncpg://"):
        value = TEST_DATABASE_URL
    elif TEST_DATABASE_URL.startswith("postgres://"):
        value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        value = TEST_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def _engine() -> AsyncEngine:
    return create_async_engine(_database_url(), poolclass=NullPool)


async def _seed(engine: AsyncEngine) -> _Fixture:
    fixture = _Fixture(*(uuid4() for _ in range(7)))
    values = asdict(fixture)
    updated_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE public.accounts CASCADE"))
        await connection.execute(
            text("INSERT INTO profiles (user_id) VALUES (:id)"),
            {"id": fixture.user_id},
        )
        await connection.execute(
            text("INSERT INTO accounts (id) VALUES (:id)"),
            {"id": fixture.account_id},
        )
        await connection.execute(
            text(
                "INSERT INTO projects "
                "(id, account_id, owner_id, title, project_type, current_context_version) "
                "VALUES (:project_id, :account_id, :user_id, 'Synthetic', 'landing', 1)"
            ),
            values,
        )
        await connection.execute(
            text(
                "INSERT INTO context_items "
                "(id, account_id, project_id, context_version, item_type, content, "
                "source_refs, status, created_by_type, updated_at) VALUES "
                "(:context_item_id, :account_id, :project_id, 1, 'fact', "
                "'synthetic fixture only', '[]'::jsonb, 'proposed', 'ai', :updated_at)"
            ),
            {**values, "updated_at": updated_at},
        )
        payload_ref = json.dumps(
            {
                "context_version": 1,
                "context_item_revisions": [
                    {
                        "context_item_id": str(fixture.context_item_id),
                        "updated_at": updated_at.isoformat(),
                    }
                ],
                "requirement_revisions": [],
                "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
                "critical_rule_pack_version": CRITICAL_GAP_RULE_PACK_VERSION,
            }
        )
        await connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, account_id, project_id, job_type, status, payload_ref, attempt_count, "
                "max_attempts, correlation_id, available_at) VALUES "
                "(:job_id, :account_id, :project_id, 'gap_detection', 'queued', "
                "CAST(:payload_ref AS jsonb), 0, 1, :correlation_id, CURRENT_TIMESTAMP)"
            ),
            {**values, "payload_ref": payload_ref},
        )
        await connection.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, account_id, aggregate_type, aggregate_id, event_type, delivery_channel, "
                "payload, status, attempt_count, available_at) VALUES "
                "(:outbox_event_id, :account_id, 'project', :project_id, "
                "'gap.detection_requested.v1', 'job_queue', CAST(:payload AS jsonb), "
                "'pending', 0, CURRENT_TIMESTAMP)"
            ),
            {
                **values,
                "payload": json.dumps(
                    {
                        "jobId": str(fixture.job_id),
                        "taskType": "gap_detection",
                        "payloadVersion": "1",
                    }
                ),
            },
        )
    return fixture


def _consumer(engine: AsyncEngine, unit_of_work_factory, ledger: _UsageLedger):
    logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=StringIO(),
    )
    use_case = DetectGapsUseCase(
        snapshot_reader=PostgresGapDetectionSnapshotReader(engine),
        ai_execution=SyntheticGapDetectionAI(),
        usage_ledger=ledger,  # type: ignore[arg-type]
        critical_rule_evaluator=VersionedCriticalGapRuleEvaluator(),
        unit_of_work_factory=unit_of_work_factory,
        event_logger=logger,
    )
    return GapDetectionConsumer(
        guard=PostgresJobExecutionGuard(engine),
        store=SqlAlchemyGapDetectionJobStore(engine),
        command_factory=SyntheticGapDetectionCommandFactory(),
        use_case=use_case,
        event_logger=logger,
    )


def test_empty_requirement_snapshot_produces_only_checklist_backed_gaps_atomically() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            ledger = _UsageLedger()
            consumer = _consumer(
                engine, PostgresGapDetectionUnitOfWorkFactory(engine), ledger
            )
            message = GapDetectionJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            assert (await consumer.execute(message)).status == "succeeded"
            assert (await consumer.execute(message)).status == "already_completed"
            async with engine.connect() as connection:
                state = (
                    await connection.execute(
                        text(
                            "SELECT status, attempt_count, payload_ref FROM jobs "
                            "WHERE id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
                counts = (
                    await connection.execute(
                        text(
                            "SELECT (SELECT count(*) FROM requirements) AS requirements, "
                            "(SELECT count(*) FROM gaps) AS gaps, "
                            "(SELECT count(*) FROM gap_requirement_links) AS links"
                        )
                    )
                ).mappings().one()
                severities = (
                    await connection.execute(
                        text("SELECT DISTINCT severity FROM gaps")
                    )
                ).scalars().all()
            assert state["status"] == "succeeded"
            assert state["attempt_count"] == 1
            assert state["payload_ref"]["gap_count"] == 3
            assert state["payload_ref"]["rule_generated_gap_count"] == 3
            assert state["payload_ref"]["critical_gap_count"] == 3
            assert counts == {"requirements": 0, "gaps": 3, "links": 0}
            assert severities == ["critical"]
            assert len(ledger.records) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_commit_failure_rolls_back_gaps_and_keeps_same_job_recoverable() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            base = PostgresGapDetectionUnitOfWorkFactory(engine)
            message = GapDetectionJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            with pytest.raises(GapDetectionRuntimePersistenceError):
                await _consumer(engine, _FailCommitFactory(base), _UsageLedger()).execute(
                    message
                )
            async with engine.connect() as connection:
                status = await connection.scalar(
                    text("SELECT status FROM jobs WHERE id=:job_id"),
                    {"job_id": fixture.job_id},
                )
                count = await connection.scalar(text("SELECT count(*) FROM gaps"))
            assert status == "running"
            assert count == 0
            assert (
                await _consumer(engine, base, _UsageLedger()).execute(message)
            ).status == "succeeded"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
