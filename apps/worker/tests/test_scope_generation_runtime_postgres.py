from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.scope_content import validate_scope_content
from aria_backend_application.scope_generation import (
    ScopeGenerationRepositoryError,
    ScopeGenerationUseCase,
)
from aria_observability import create_event_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncTransaction, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.scope_generation_consumer import (
    ExplicitSyntheticScopeProjects,
    ScopeGenerationConsumer,
    ScopeGenerationJobMessage,
    ScopeGenerationRuntimePersistenceError,
)
from app.application.scope_generation_runtime import SyntheticScopeGenerationCommandFactory
from app.infrastructure.ai.synthetic_scope_generation import SyntheticScopeGenerationAI
from app.infrastructure.db.scope_generation_runtime import (
    PostgresScopeGenerationFinalizer,
    PostgresScopeGenerationSnapshotReader,
    SqlAlchemyScopeGenerationJobStore,
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
    requirement_id: UUID
    job_id: UUID
    outbox_event_id: UUID
    correlation_id: UUID


class _UsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class _Validator:
    def validate(self, content: object) -> dict[str, object]:
        return validate_scope_content(content)


class _FailCommitFinalizer(PostgresScopeGenerationFinalizer):
    async def _commit(self, transaction: AsyncTransaction) -> None:
        del transaction
        raise ScopeGenerationRepositoryError("synthetic_commit_failure")


class _ChangingInputsAI(SyntheticScopeGenerationAI):
    def __init__(self, engine: AsyncEngine, requirement_id: UUID) -> None:
        super().__init__()
        self._engine = engine
        self._requirement_id = requirement_id

    async def execute_structured(self, **kwargs: object) -> StructuredAIResponse:
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE public.requirements SET title='Changed after fake AI' "
                    "WHERE id=:id"
                ),
                {"id": self._requirement_id},
            )
        return await super().execute_structured(**kwargs)  # type: ignore[arg-type]


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def _engine(*, worker_role: bool = False) -> AsyncEngine:
    connect_args = {"server_settings": {"role": "aria_worker"}} if worker_role else {}
    return create_async_engine(_database_url(), poolclass=NullPool, connect_args=connect_args)


async def _seed(engine: AsyncEngine) -> _Fixture:
    fixture = _Fixture(*(uuid4() for _ in range(8)))
    values = asdict(fixture)
    updated_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE public.accounts CASCADE"))
        await connection.execute(
            text("INSERT INTO public.profiles (user_id) VALUES (:user_id)"), values
        )
        await connection.execute(
            text("INSERT INTO public.accounts (id) VALUES (:account_id)"), values
        )
        await connection.execute(
            text(
                "INSERT INTO public.projects "
                "(id, account_id, owner_id, title, project_type, current_context_version) "
                "VALUES (:project_id, :account_id, :user_id, 'Synthetic', 'landing', 1)"
            ),
            values,
        )
        await connection.execute(
            text(
                "INSERT INTO public.context_items "
                "(id, account_id, project_id, context_version, item_type, content, "
                "source_refs, status, created_by_type, updated_at) VALUES "
                "(:context_item_id, :account_id, :project_id, 1, 'fact', "
                "'synthetic fixture only', '[]'::jsonb, 'proposed', 'ai', :updated_at)"
            ),
            {**values, "updated_at": updated_at},
        )
        await connection.execute(
            text(
                "INSERT INTO public.requirements "
                "(id, account_id, project_id, context_version, category, title, "
                "description, priority, status, created_by_type, updated_at) VALUES "
                "(:requirement_id, :account_id, :project_id, 1, 'functional', "
                "'Synthetic requirement', 'Synthetic only', 'must', 'draft', 'ai', "
                ":updated_at)"
            ),
            {**values, "updated_at": updated_at},
        )
        revisions = lambda name: [  # noqa: E731
            {"id": str(values[name]), "updated_at": updated_at.isoformat()}
        ]
        payload_ref = json.dumps(
            {
                "context_version": 1,
                "context_item_revisions": revisions("context_item_id"),
                "requirement_revisions": revisions("requirement_id"),
                "gap_revisions": [],
            }
        )
        await connection.execute(
            text(
                "INSERT INTO public.jobs "
                "(id, account_id, project_id, job_type, status, payload_ref, "
                "attempt_count, max_attempts, correlation_id, available_at) VALUES "
                "(:job_id, :account_id, :project_id, 'scope_generation', 'queued', "
                "CAST(:payload_ref AS jsonb), 0, 1, :correlation_id, CURRENT_TIMESTAMP)"
            ),
            {**values, "payload_ref": payload_ref},
        )
        await connection.execute(
            text(
                "INSERT INTO public.outbox_events "
                "(id, account_id, aggregate_type, aggregate_id, event_type, "
                "delivery_channel, payload, status, attempt_count, available_at) VALUES "
                "(:outbox_event_id, :account_id, 'project', :project_id, "
                "'scope.generation_requested.v1', 'job_queue', CAST(:payload AS jsonb), "
                "'pending', 0, CURRENT_TIMESTAMP)"
            ),
            {
                **values,
                "payload": json.dumps(
                    {
                        "jobId": str(fixture.job_id),
                        "taskType": "scope_generation",
                        "payloadVersion": "1",
                    }
                ),
            },
        )
    return fixture


def _consumer(
    engine: AsyncEngine,
    fixture: _Fixture,
    ledger: _UsageLedger,
    finalizer: PostgresScopeGenerationFinalizer | None = None,
    ai: SyntheticScopeGenerationAI | None = None,
) -> ScopeGenerationConsumer:
    logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=StringIO(),
    )
    use_case = ScopeGenerationUseCase(
        snapshot_reader=PostgresScopeGenerationSnapshotReader(engine),
        ai_execution=ai or SyntheticScopeGenerationAI(),
        usage_ledger=ledger,  # type: ignore[arg-type]
        content_validator=_Validator(),
        finalizer=finalizer or PostgresScopeGenerationFinalizer(engine),
        event_logger=logger,
    )
    return ScopeGenerationConsumer(
        guard=PostgresJobExecutionGuard(engine),
        store=SqlAlchemyScopeGenerationJobStore(engine),
        command_factory=SyntheticScopeGenerationCommandFactory(),
        use_case=use_case,
        synthetic_authorizer=ExplicitSyntheticScopeProjects(
            frozenset({(fixture.account_id, fixture.project_id)})
        ),
        event_logger=logger,
    )


def test_synthetic_scope_finalization_and_duplicate_delivery() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            ledger = _UsageLedger()
            consumer = _consumer(engine, fixture, ledger)
            message = ScopeGenerationJobMessage("1", fixture.outbox_event_id, fixture.job_id)
            assert (await consumer.execute(message)).status == "succeeded"
            assert (await consumer.execute(message)).status == "already_completed"
            async with engine.connect() as connection:
                state = await connection.scalar(
                    text("SELECT status FROM public.jobs WHERE id=:id"), {"id": fixture.job_id}
                )
                count = await connection.scalar(text("SELECT count(*) FROM public.scope_drafts"))
            assert state == "succeeded"
            assert count == 1
            assert len(ledger.records) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_role_has_only_required_runtime_access() -> None:
    async def scenario() -> None:
        owner_engine = _engine()
        worker_engine = _engine(worker_role=True)
        try:
            fixture = await _seed(owner_engine)
            message = ScopeGenerationJobMessage("1", fixture.outbox_event_id, fixture.job_id)
            assert (
                await _consumer(worker_engine, fixture, _UsageLedger()).execute(message)
            ).status == "succeeded"
            async with owner_engine.connect() as connection:
                count = await connection.scalar(text("SELECT count(*) FROM public.scope_drafts"))
            assert count == 1
        finally:
            await worker_engine.dispose()
            await owner_engine.dispose()

    asyncio.run(scenario())


def test_changed_pinned_input_fails_without_provider_or_draft() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE public.requirements SET title='Changed synthetic input' "
                        "WHERE id=:id"
                    ),
                    {"id": fixture.requirement_id},
                )
            ledger = _UsageLedger()
            message = ScopeGenerationJobMessage("1", fixture.outbox_event_id, fixture.job_id)
            result = await _consumer(engine, fixture, ledger).execute(message)
            assert result.status == "failed"
            assert result.error_code == "SCOPE_GENERATION_INPUT_CHANGED"
            async with engine.connect() as connection:
                count = await connection.scalar(text("SELECT count(*) FROM public.scope_drafts"))
            assert count == 0
            assert ledger.records == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_input_changed_after_fake_ai_rejects_atomic_finalization() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            ledger = _UsageLedger()
            message = ScopeGenerationJobMessage("1", fixture.outbox_event_id, fixture.job_id)
            result = await _consumer(
                engine, fixture, ledger,
                ai=_ChangingInputsAI(engine, fixture.requirement_id),
            ).execute(message)
            assert result.status == "failed"
            assert result.error_code == "SCOPE_GENERATION_INPUT_CHANGED"
            async with engine.connect() as connection:
                count = await connection.scalar(text("SELECT count(*) FROM public.scope_drafts"))
                status = await connection.scalar(
                    text("SELECT status FROM public.jobs WHERE id=:id"),
                    {"id": fixture.job_id},
                )
            assert count == 0
            assert status == "failed"
            assert len(ledger.records) == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_failed_commit_rolls_back_draft_and_job_success_then_recovers() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            message = ScopeGenerationJobMessage("1", fixture.outbox_event_id, fixture.job_id)
            with pytest.raises(ScopeGenerationRuntimePersistenceError):
                await _consumer(
                    engine, fixture, _UsageLedger(), _FailCommitFinalizer(engine)
                ).execute(message)
            async with engine.connect() as connection:
                state = await connection.scalar(
                    text("SELECT status FROM public.jobs WHERE id=:id"), {"id": fixture.job_id}
                )
                count = await connection.scalar(text("SELECT count(*) FROM public.scope_drafts"))
            assert state == "running"
            assert count == 0
            assert (
                await _consumer(engine, fixture, _UsageLedger()).execute(message)
            ).status == "succeeded"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
