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
from aria_backend_application.requirements_generation import (
    GenerateRequirementsUseCase,
    RequirementGenerationRepositoryError,
    RequirementGenerationUnitOfWork,
)
from aria_observability import create_event_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.requirement_generation_consumer import (
    RequirementGenerationConsumer,
    RequirementGenerationJobMessage,
    RequirementGenerationRuntimePersistenceError,
)
from app.application.requirement_generation_runtime import (
    SyntheticRequirementGenerationCommandFactory,
)
from app.infrastructure.ai.synthetic_requirement_generation import (
    SyntheticRequirementGenerationAI,
)
from app.infrastructure.db.requirement_generation_runtime import (
    PostgresRequirementContextSnapshotReader,
    PostgresRequirementGenerationUnitOfWorkFactory,
    SqlAlchemyRequirementGenerationJobStore,
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
    source_id: UUID
    source_version_id: UUID
    context_item_id: UUID
    job_id: UUID
    outbox_event_id: UUID
    correlation_id: UUID


class _UsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class _SupportValidator:
    async def validate(self, *, batch: object, snapshot: object) -> None:
        del batch, snapshot


class _FailCommitUnitOfWork:
    def __init__(self, inner: RequirementGenerationUnitOfWork) -> None:
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
        raise RequirementGenerationRepositoryError("synthetic_commit_failure")


class _FailCommitFactory:
    def __init__(self, inner: PostgresRequirementGenerationUnitOfWorkFactory) -> None:
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
    fixture = _Fixture(*(uuid4() for _ in range(9)))
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
            {
                "project_id": fixture.project_id,
                "account_id": fixture.account_id,
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO context_sources "
                "(id, account_id, project_id, source_type, status, created_by) "
                "VALUES (:source_id, :account_id, :project_id, 'text', 'ready', :user_id)"
            ),
            values,
        )
        await connection.execute(
            text(
                "INSERT INTO context_source_versions "
                "(id, account_id, project_id, source_id, version_no, canonical_text, "
                "parse_status) VALUES (:source_version_id, :account_id, :project_id, "
                ":source_id, 1, 'synthetic fixture only', 'ready')"
            ),
            values,
        )
        source_refs = json.dumps(
            [
                {
                    "source_id": str(fixture.source_id),
                    "source_version_id": str(fixture.source_version_id),
                }
            ]
        )
        await connection.execute(
            text(
                "INSERT INTO context_items "
                "(id, account_id, project_id, context_version, item_type, content, "
                "source_refs, status, created_by_type, updated_at) VALUES "
                "(:context_item_id, :account_id, :project_id, 1, 'fact', "
                "'synthetic fixture only', CAST(:source_refs AS jsonb), 'confirmed', 'ai', "
                ":updated_at)"
            ),
            {**values, "source_refs": source_refs, "updated_at": updated_at},
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
            }
        )
        await connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, account_id, project_id, job_type, status, payload_ref, attempt_count, "
                "max_attempts, correlation_id, available_at) VALUES "
                "(:job_id, :account_id, :project_id, 'requirement_generation', 'queued', "
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
                "'requirement.generation_requested.v1', 'job_queue', "
                "CAST(:payload AS jsonb), 'pending', 0, CURRENT_TIMESTAMP)"
            ),
            {
                **values,
                "payload": json.dumps(
                    {
                        "jobId": str(fixture.job_id),
                        "taskType": "requirement_generation",
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
    use_case = GenerateRequirementsUseCase(
        snapshot_reader=PostgresRequirementContextSnapshotReader(engine),
        ai_execution=SyntheticRequirementGenerationAI(),
        usage_ledger=ledger,  # type: ignore[arg-type]
        support_validator=_SupportValidator(),  # type: ignore[arg-type]
        unit_of_work_factory=unit_of_work_factory,
        event_logger=logger,
    )
    return RequirementGenerationConsumer(
        guard=PostgresJobExecutionGuard(engine),
        store=SqlAlchemyRequirementGenerationJobStore(engine),
        command_factory=SyntheticRequirementGenerationCommandFactory(),
        use_case=use_case,
        event_logger=logger,
    )


def test_atomic_success_and_duplicate_delivery_do_not_duplicate_requirements() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            ledger = _UsageLedger()
            consumer = _consumer(
                engine,
                PostgresRequirementGenerationUnitOfWorkFactory(engine),
                ledger,
            )
            message = RequirementGenerationJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            assert (await consumer.execute(message)).status == "succeeded"
            assert (await consumer.execute(message)).status == "already_completed"
            async with engine.connect() as connection:
                state = (
                    await connection.execute(
                        text(
                            "SELECT status, attempt_count FROM jobs WHERE id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
                count = await connection.scalar(
                    text("SELECT count(*) FROM requirements WHERE project_id=:project_id"),
                    {"project_id": fixture.project_id},
                )
            assert state == {"status": "succeeded", "attempt_count": 1}
            assert count == 1
            assert len(ledger.records) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_commit_failure_rolls_back_requirements_and_keeps_same_job_recoverable() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            base = PostgresRequirementGenerationUnitOfWorkFactory(engine)
            message = RequirementGenerationJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            with pytest.raises(RequirementGenerationRuntimePersistenceError):
                await _consumer(engine, _FailCommitFactory(base), _UsageLedger()).execute(
                    message
                )
            async with engine.connect() as connection:
                status = await connection.scalar(
                    text("SELECT status FROM jobs WHERE id=:job_id"),
                    {"job_id": fixture.job_id},
                )
                count = await connection.scalar(text("SELECT count(*) FROM requirements"))
            assert status == "running"
            assert count == 0
            assert (await _consumer(engine, base, _UsageLedger()).execute(message)).status == (
                "succeeded"
            )
        finally:
            await engine.dispose()

    asyncio.run(scenario())
