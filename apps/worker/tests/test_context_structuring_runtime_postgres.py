from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_backend_application.context_structuring import (
    ContextRepairPolicy,
    ContextStructuringCommand,
    ContextStructuringRepositoryError,
    ContextStructuringUnitOfWork,
    ContextStructuringUseCase,
)
from aria_observability import create_event_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.context_structuring_consumer import (
    ContextStructuringConsumer,
    ContextStructuringJobInput,
    ContextStructuringJobMessage,
    ContextStructuringRuntimePersistenceError,
)
from app.infrastructure.ai.synthetic_context_structuring import (
    SyntheticContextStructuringAI,
)
from app.infrastructure.db.context_structuring_runtime import (
    PostgresContextStructuringSnapshotReader,
    PostgresContextStructuringUnitOfWorkFactory,
    SqlAlchemyContextStructuringJobStore,
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
    job_id: UUID
    outbox_event_id: UUID
    correlation_id: UUID


class _UsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class _UnsupportedClaimValidator:
    async def validate(self, *, batch: object, snapshot: object) -> None:
        del batch, snapshot


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


class _FailCommitUnitOfWork:
    def __init__(self, inner: ContextStructuringUnitOfWork) -> None:
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
        raise ContextStructuringRepositoryError("synthetic_commit_failure")


class _FailCommitFactory:
    def __init__(self, inner: PostgresContextStructuringUnitOfWorkFactory) -> None:
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
    fixture = _Fixture(*(uuid4() for _ in range(8)))
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE public.accounts CASCADE"))
        await connection.execute(
            text("INSERT INTO profiles (user_id) VALUES (:user_id)"),
            {"user_id": fixture.user_id},
        )
        await connection.execute(
            text("INSERT INTO accounts (id) VALUES (:account_id)"),
            {"account_id": fixture.account_id},
        )
        await connection.execute(
            text(
                "INSERT INTO account_memberships "
                "(id, account_id, user_id, role, status) "
                "VALUES (:id, :account_id, :user_id, 'owner', 'active')"
            ),
            {
                "id": uuid4(),
                "account_id": fixture.account_id,
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
                "VALUES (:project_id, :account_id, :user_id, 'Synthetic', 'landing')"
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
            {
                "source_id": fixture.source_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO context_source_versions "
                "(id, account_id, project_id, source_id, version_no, canonical_text, "
                "parse_status) VALUES (:version_id, :account_id, :project_id, "
                ":source_id, 1, :canonical_text, 'ready')"
            ),
            {
                "version_id": fixture.source_version_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "source_id": fixture.source_id,
                "canonical_text": "محتوای محرمانه آزمایشی 0071",
            },
        )
        await connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, account_id, project_id, job_type, status, payload_ref, "
                "attempt_count, max_attempts, correlation_id, available_at) "
                "VALUES (:job_id, :account_id, :project_id, 'context_structuring', "
                "'queued', NULL, 0, 1, :correlation_id, CURRENT_TIMESTAMP)"
            ),
            {
                "job_id": fixture.job_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "correlation_id": fixture.correlation_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, account_id, aggregate_type, aggregate_id, event_type, "
                "delivery_channel, payload, status, attempt_count, available_at) "
                "VALUES (:event_id, :account_id, 'project', :project_id, "
                "'context.structuring_requested.v1', 'job_queue', "
                "CAST(:payload AS jsonb), 'pending', 0, CURRENT_TIMESTAMP)"
            ),
            {
                "event_id": fixture.outbox_event_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "payload": json.dumps(
                    {
                        "jobId": str(fixture.job_id),
                        "taskType": "context_structuring",
                        "payloadVersion": "1",
                    }
                ),
            },
        )
    return fixture


def _consumer(
    *,
    engine: AsyncEngine,
    unit_of_work_factory,
    ledger: _UsageLedger,
    stream: StringIO,
) -> ContextStructuringConsumer:
    event_logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    use_case = ContextStructuringUseCase(
        snapshot_reader=PostgresContextStructuringSnapshotReader(engine),
        ai_execution=SyntheticContextStructuringAI(),
        usage_ledger=ledger,  # type: ignore[arg-type]
        unsupported_claim_validator=_UnsupportedClaimValidator(),  # type: ignore[arg-type]
        unit_of_work_factory=unit_of_work_factory,
        event_logger=event_logger,
    )
    return ContextStructuringConsumer(
        guard=PostgresJobExecutionGuard(engine),
        store=SqlAlchemyContextStructuringJobStore(engine),
        command_factory=_CommandFactory(),
        use_case=use_case,
        event_logger=event_logger,
    )


def test_atomic_success_and_duplicate_delivery_reuse_the_same_job() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            ledger, stream = _UsageLedger(), StringIO()
            consumer = _consumer(
                engine=engine,
                unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(engine),
                ledger=ledger,
                stream=stream,
            )
            message = ContextStructuringJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            assert (await consumer.execute(message)).status == "succeeded"
            assert (await consumer.execute(message)).status == "already_completed"

            async with engine.connect() as connection:
                state = (
                    await connection.execute(
                        text(
                            "SELECT j.status, j.attempt_count, p.current_context_version "
                            "FROM jobs AS j JOIN projects AS p ON p.id=j.project_id "
                            "WHERE j.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
                item_count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM context_items "
                        "WHERE account_id=:account_id AND project_id=:project_id"
                    ),
                    {
                        "account_id": fixture.account_id,
                        "project_id": fixture.project_id,
                    },
                )
            assert state == {
                "status": "succeeded",
                "attempt_count": 1,
                "current_context_version": 1,
            }
            assert item_count == 1
            assert len(ledger.records) == 1
            assert "محتوای محرمانه آزمایشی 0071" not in stream.getvalue()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failed_commit_rolls_back_domain_state_and_fake_recovery_is_safe() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            message = ContextStructuringJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            base_factory = PostgresContextStructuringUnitOfWorkFactory(engine)
            interrupted = _consumer(
                engine=engine,
                unit_of_work_factory=_FailCommitFactory(base_factory),
                ledger=_UsageLedger(),
                stream=StringIO(),
            )
            with pytest.raises(ContextStructuringRuntimePersistenceError):
                await interrupted.execute(message)

            async with engine.connect() as connection:
                interrupted_state = (
                    await connection.execute(
                        text(
                            "SELECT j.status, p.current_context_version, "
                            "(SELECT count(*) FROM context_items WHERE project_id=p.id) "
                            "AS item_count FROM jobs AS j "
                            "JOIN projects AS p ON p.id=j.project_id "
                            "WHERE j.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert interrupted_state == {
                "status": "running",
                "current_context_version": 0,
                "item_count": 0,
            }

            recovered = _consumer(
                engine=engine,
                unit_of_work_factory=base_factory,
                ledger=_UsageLedger(),
                stream=StringIO(),
            )
            assert (await recovered.execute(message)).status == "succeeded"
            async with engine.connect() as connection:
                recovered_state = (
                    await connection.execute(
                        text(
                            "SELECT j.status, j.attempt_count, p.current_context_version, "
                            "(SELECT count(*) FROM context_items WHERE project_id=p.id) "
                            "AS item_count FROM jobs AS j "
                            "JOIN projects AS p ON p.id=j.project_id "
                            "WHERE j.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert recovered_state == {
                "status": "succeeded",
                "attempt_count": 1,
                "current_context_version": 1,
                "item_count": 1,
            }
        finally:
            await engine.dispose()

    asyncio.run(scenario())
