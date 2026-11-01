from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_execution import AIExecutionError
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
from app.infrastructure.ai.context_structuring_checkpoint import (
    SyntheticAI01CheckpointRuntime,
)
from app.infrastructure.ai.synthetic_context_structuring import (
    SyntheticContextStructuringAI,
)
from app.infrastructure.db.ai_invocation_recovery import (
    PostgresAIInvocationCheckpointStore,
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


class _CountingSyntheticAI(SyntheticContextStructuringAI):
    def __init__(self) -> None:
        super().__init__()
        self.invocations = 0

    async def execute_structured(self, *args, **kwargs):
        self.invocations += 1
        return await super().execute_structured(*args, **kwargs)


class _TimeoutThenSyntheticAI(_CountingSyntheticAI):
    async def execute_structured(self, *args, **kwargs):
        self.invocations += 1
        if self.invocations == 1:
            raise AIExecutionError("timeout", retryable=True)
        return await SyntheticContextStructuringAI.execute_structured(
            self, *args, **kwargs
        )


class _AlwaysTimeoutAI(_CountingSyntheticAI):
    async def execute_structured(self, *args, **kwargs):
        del args, kwargs
        self.invocations += 1
        raise AIExecutionError("timeout", retryable=True)


class _RecordingSleeper:
    def __init__(self, *, crash: bool = False) -> None:
        self.delays: list[float] = []
        self._crash = crash

    async def sleep(self, delay_seconds: float) -> None:
        self.delays.append(delay_seconds)
        if self._crash:
            raise KeyboardInterrupt("synthetic crash after failed_known commit")


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
            output_schema_version="context-structuring-output-v1",
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


def _engine(*, worker: bool = False) -> AsyncEngine:
    options: dict[str, object] = {"poolclass": NullPool}
    if worker:
        options["connect_args"] = {"server_settings": {"role": "aria_worker"}}
    return create_async_engine(_database_url(), **options)  # type: ignore[arg-type]


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
                "content_hash, parse_status) VALUES (:version_id, :account_id, :project_id, "
                ":source_id, 1, :canonical_text, :content_hash, 'ready')"
            ),
            {
                "version_id": fixture.source_version_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "source_id": fixture.source_id,
                "canonical_text": "محتوای محرمانه آزمایشی 0071",
                "content_hash": "a" * 64,
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
                "INSERT INTO provider_price_versions "
                "(provider, model, pricing_version, currency, input_rate_per_1m, "
                "cached_input_rate_per_1m, output_rate_per_1m, effective_from) "
                "VALUES ('synthetic', 'context-structuring-fake-v1', "
                "'synthetic-zero-v1', 'USD', 0, 0, 0, "
                "TIMESTAMPTZ '2026-01-01 00:00:00+00') "
                "ON CONFLICT DO NOTHING"
            )
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


def _checkpoint_consumer(
    *,
    engine: AsyncEngine,
    unit_of_work_factory,
    ai: SyntheticContextStructuringAI,
    stream: StringIO,
    timeout_retry_enabled: bool = False,
    utc_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    random_source: Callable[[], float] = lambda: 0.5,
    sleeper: _RecordingSleeper | None = None,
) -> ContextStructuringConsumer:
    event_logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    checkpoint = SyntheticAI01CheckpointRuntime(
        PostgresAIInvocationCheckpointStore(engine),
        timeout_retry_enabled=timeout_retry_enabled,
        utc_clock=utc_clock,
        random_source=random_source,
        sleeper=sleeper,
    )
    use_case = ContextStructuringUseCase(
        snapshot_reader=PostgresContextStructuringSnapshotReader(engine),
        ai_execution=ai,
        usage_ledger=None,
        checkpoint_runtime=checkpoint,
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


def test_checkpoint_recovery_finalizes_same_attempt_without_second_invocation() -> None:
    async def scenario() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            message = ContextStructuringJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            ai = _CountingSyntheticAI()
            stream = StringIO()
            base_factory = PostgresContextStructuringUnitOfWorkFactory(worker)
            interrupted = _checkpoint_consumer(
                engine=worker,
                unit_of_work_factory=_FailCommitFactory(base_factory),
                ai=ai,
                stream=stream,
            )
            with pytest.raises(ContextStructuringRuntimePersistenceError):
                await interrupted.execute(message)

            async with owner.connect() as connection:
                interrupted_state = (
                    await connection.execute(
                        text(
                            "SELECT j.status, p.current_context_version, "
                            "checkpoint.status AS checkpoint_status, "
                            "checkpoint.normalized_result IS NOT NULL AS payload_retained, "
                            "(SELECT count(*) FROM public.usage_records "
                            " WHERE job_id=j.id) AS usage_count, "
                            "(SELECT count(*) FROM public.context_items "
                            " WHERE project_id=p.id) AS item_count "
                            "FROM public.jobs AS j "
                            "JOIN public.projects AS p ON p.id=j.project_id "
                            "JOIN public.ai_invocation_checkpoints AS checkpoint "
                            "ON checkpoint.job_id=j.id WHERE j.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert interrupted_state == {
                "status": "running",
                "current_context_version": 0,
                "checkpoint_status": "result_ready",
                "payload_retained": True,
                "usage_count": 1,
                "item_count": 0,
            }
            assert ai.invocations == 1

            recovered = _checkpoint_consumer(
                engine=worker,
                unit_of_work_factory=base_factory,
                ai=ai,
                stream=stream,
            )
            assert (await recovered.execute(message)).status == "succeeded"

            async with owner.connect() as connection:
                final_state = (
                    await connection.execute(
                        text(
                            "SELECT j.status, p.current_context_version, "
                            "checkpoint.status AS checkpoint_status, "
                            "checkpoint.normalized_result IS NULL AS payload_cleared, "
                            "checkpoint.normalized_result_hash IS NOT NULL AS hash_retained, "
                            "(SELECT count(*) FROM public.usage_records "
                            " WHERE job_id=j.id) AS usage_count, "
                            "(SELECT count(*) FROM public.context_items "
                            " WHERE project_id=p.id) AS item_count "
                            "FROM public.jobs AS j "
                            "JOIN public.projects AS p ON p.id=j.project_id "
                            "JOIN public.ai_invocation_checkpoints AS checkpoint "
                            "ON checkpoint.job_id=j.id WHERE j.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert final_state == {
                "status": "succeeded",
                "current_context_version": 1,
                "checkpoint_status": "finalized",
                "payload_cleared": True,
                "hash_retained": True,
                "usage_count": 1,
                "item_count": 1,
            }
            assert ai.invocations == 1
            assert "محتوای محرمانه آزمایشی 0071" not in stream.getvalue()
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())


def test_durable_timeout_retry_persists_two_attempts_and_two_usage_records() -> None:
    async def scenario() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            message = ContextStructuringJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            now = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
            sleeper = _RecordingSleeper()
            ai = _TimeoutThenSyntheticAI()
            consumer = _checkpoint_consumer(
                engine=worker,
                unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(worker),
                ai=ai,
                stream=StringIO(),
                timeout_retry_enabled=True,
                utc_clock=lambda: now,
                random_source=lambda: 0.5,
                sleeper=sleeper,
            )

            assert (await consumer.execute(message)).status == "succeeded"

            async with owner.connect() as connection:
                attempts = (
                    await connection.execute(
                        text(
                            "SELECT provider_attempt_id, status, failure_class, retryable, "
                            "retry_not_before, retry_no, input_fingerprint "
                            "FROM ai_invocation_checkpoints WHERE job_id=:job_id "
                            "ORDER BY retry_no"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().all()
                usage = (
                    await connection.execute(
                        text(
                            "SELECT provider_attempt_id, status, accounting_status, "
                            "input_tokens, cached_input_tokens, output_tokens, "
                            "estimated_cost, retry_no FROM usage_records "
                            "WHERE job_id=:job_id ORDER BY retry_no"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().all()
                version = await connection.scalar(
                    text(
                        "SELECT current_context_version FROM projects "
                        "WHERE id=:project_id"
                    ),
                    {"project_id": fixture.project_id},
                )

            assert ai.invocations == 2
            assert sleeper.delays == [1.0]
            assert len(attempts) == len(usage) == 2
            assert attempts[0]["status"] == "failed_known"
            assert attempts[0]["failure_class"] == "timeout"
            assert attempts[0]["retryable"] is True
            assert attempts[0]["retry_not_before"] == now + timedelta(seconds=1)
            assert attempts[1]["status"] == "finalized"
            assert attempts[1]["retry_not_before"] is None
            assert attempts[0]["input_fingerprint"] == attempts[1]["input_fingerprint"]
            assert attempts[0]["provider_attempt_id"] != attempts[1]["provider_attempt_id"]
            assert usage[0]["provider_attempt_id"] == attempts[0]["provider_attempt_id"]
            assert usage[0]["status"] == "failed"
            assert usage[0]["accounting_status"] == "unavailable"
            assert all(
                usage[0][field] is None
                for field in (
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "estimated_cost",
                )
            )
            assert usage[1]["provider_attempt_id"] == attempts[1]["provider_attempt_id"]
            assert usage[1]["status"] == "success"
            assert usage[1]["accounting_status"] == "complete"
            assert version == 1
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())


def test_crash_after_failed_known_reuses_schedule_and_never_reinvokes_attempt_zero() -> None:
    async def scenario() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            message = ContextStructuringJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            scheduled_from = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
            first_ai = _TimeoutThenSyntheticAI()
            interrupted = _checkpoint_consumer(
                engine=worker,
                unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(worker),
                ai=first_ai,
                stream=StringIO(),
                timeout_retry_enabled=True,
                utc_clock=lambda: scheduled_from,
                random_source=lambda: 0.5,
                sleeper=_RecordingSleeper(crash=True),
            )
            with pytest.raises(KeyboardInterrupt):
                await interrupted.execute(message)

            async with owner.connect() as connection:
                interrupted_state = (
                    await connection.execute(
                        text(
                            "SELECT checkpoint.status, checkpoint.retry_not_before, "
                            "job.status AS job_status, "
                            "(SELECT count(*) FROM ai_invocation_checkpoints c "
                            " WHERE c.job_id=job.id) AS attempt_count, "
                            "(SELECT count(*) FROM usage_records u "
                            " WHERE u.job_id=job.id) AS usage_count "
                            "FROM jobs AS job JOIN ai_invocation_checkpoints AS checkpoint "
                            "ON checkpoint.job_id=job.id AND checkpoint.retry_no=0 "
                            "WHERE job.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert interrupted_state == {
                "status": "failed_known",
                "retry_not_before": scheduled_from + timedelta(seconds=1),
                "job_status": "running",
                "attempt_count": 1,
                "usage_count": 1,
            }
            assert first_ai.invocations == 1

            recovered_ai = _CountingSyntheticAI()
            recovery_sleeper = _RecordingSleeper()
            recovered = _checkpoint_consumer(
                engine=worker,
                unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(worker),
                ai=recovered_ai,
                stream=StringIO(),
                timeout_retry_enabled=True,
                utc_clock=lambda: scheduled_from + timedelta(seconds=2),
                random_source=lambda: 0.0,
                sleeper=recovery_sleeper,
            )
            assert (await recovered.execute(message)).status == "succeeded"

            async with owner.connect() as connection:
                final = (
                    await connection.execute(
                        text(
                            "SELECT job.status, project.current_context_version, "
                            "(SELECT count(*) FROM ai_invocation_checkpoints c "
                            " WHERE c.job_id=job.id) AS attempt_count, "
                            "(SELECT count(*) FROM usage_records u "
                            " WHERE u.job_id=job.id) AS usage_count "
                            "FROM jobs AS job JOIN projects AS project "
                            "ON project.id=job.project_id WHERE job.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert final == {
                "status": "succeeded",
                "current_context_version": 1,
                "attempt_count": 2,
                "usage_count": 2,
            }
            assert first_ai.invocations == 1
            assert recovered_ai.invocations == 1
            assert recovery_sleeper.delays == []
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())


def test_second_timeout_is_terminal_and_never_creates_attempt_two() -> None:
    async def scenario() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            message = ContextStructuringJobMessage(
                "1", fixture.outbox_event_id, fixture.job_id
            )
            now = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
            ai = _AlwaysTimeoutAI()
            consumer = _checkpoint_consumer(
                engine=worker,
                unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(worker),
                ai=ai,
                stream=StringIO(),
                timeout_retry_enabled=True,
                utc_clock=lambda: now,
                random_source=lambda: 0.0,
                sleeper=_RecordingSleeper(),
            )

            result = await consumer.execute(message)
            assert result.status == "failed"
            assert result.error_code == "TIMEOUT"

            async with owner.connect() as connection:
                state = (
                    await connection.execute(
                        text(
                            "SELECT job.status, job.error_code, "
                            "(SELECT count(*) FROM ai_invocation_checkpoints c "
                            " WHERE c.job_id=job.id) AS attempt_count, "
                            "(SELECT max(retry_no) FROM ai_invocation_checkpoints c "
                            " WHERE c.job_id=job.id) AS max_retry_no, "
                            "(SELECT count(*) FROM usage_records u "
                            " WHERE u.job_id=job.id) AS usage_count "
                            "FROM jobs AS job WHERE job.id=:job_id"
                        ),
                        {"job_id": fixture.job_id},
                    )
                ).mappings().one()
            assert state == {
                "status": "failed",
                "error_code": "TIMEOUT",
                "attempt_count": 2,
                "max_retry_no": 1,
                "usage_count": 2,
            }
            assert ai.invocations == 2
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())
