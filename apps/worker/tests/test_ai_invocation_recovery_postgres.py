from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_invocation_recovery import (
    AI_INVOCATION_OUTCOME_UNKNOWN,
    AIInvocationAttempt,
    AIInvocationRecoveryError,
    DurableAIInvocationRecovery,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.db.ai_invocation_recovery import (
    PostgresAIInvocationCheckpointStore,
    complete_usage_record,
    unavailable_usage_record,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


@dataclass(frozen=True, slots=True)
class Fixture:
    user_id: UUID
    account_id: UUID
    project_id: UUID
    job_id: UUID
    correlation_id: UUID
    provider: str
    model: str
    pricing_version: str


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def _engine(*, worker: bool = False) -> AsyncEngine:
    options: dict[str, object] = {"poolclass": NullPool}
    if worker:
        options["connect_args"] = {"server_settings": {"role": "aria_worker"}}
    return create_async_engine(_database_url(), **options)  # type: ignore[arg-type]


async def _seed(engine: AsyncEngine) -> Fixture:
    suffix = uuid4().hex
    fixture = Fixture(
        user_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        job_id=uuid4(),
        correlation_id=uuid4(),
        provider=f"synthetic-{suffix}",
        model=f"synthetic-model-{suffix}",
        pricing_version=f"synthetic-price-{suffix}",
    )
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
            {"id": uuid4(), "account_id": fixture.account_id, "user_id": fixture.user_id},
        )
        await connection.execute(
            text(
                "INSERT INTO projects "
                "(id, account_id, owner_id, title, project_type) "
                "VALUES (:project_id, :account_id, :user_id, 'Synthetic 0083', 'landing')"
            ),
            {
                "project_id": fixture.project_id,
                "account_id": fixture.account_id,
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, account_id, project_id, job_type, status, payload_ref, "
                "attempt_count, max_attempts, correlation_id, available_at, started_at) "
                "VALUES (:job_id, :account_id, :project_id, 'context_structuring', "
                "'running', NULL, 1, 1, :correlation_id, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
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
                "VALUES (:provider, :model, :pricing_version, 'USD', 0, 0, 0, "
                ":effective_from)"
            ),
            {
                "provider": fixture.provider,
                "model": fixture.model,
                "pricing_version": fixture.pricing_version,
                "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )
    return fixture


def _attempt(fixture: Fixture) -> AIInvocationAttempt:
    return AIInvocationAttempt(
        provider_attempt_id=uuid4(),
        account_id=fixture.account_id,
        project_id=fixture.project_id,
        job_id=fixture.job_id,
        task_type="context_structuring",
        workflow_version="synthetic-ai-01-v1",
        prompt_version="synthetic-prompt-v1",
        output_schema_version="context-batch-v1",
        provider=fixture.provider,
        model=fixture.model,
        pricing_version=fixture.pricing_version,
        input_fingerprint="b" * 64,
        retry_no=0,
        repair_no=0,
        correlation_id=fixture.correlation_id,
    )


def test_checkpoint_recovery_reuses_result_and_cleanup_removes_payload() -> None:
    async def exercise() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            attempt = _attempt(fixture)
            recovery = DurableAIInvocationRecovery(
                PostgresAIInvocationCheckpointStore(worker)
            )
            result = {"items": [{"item_type": "fact", "content": "synthetic-only"}]}

            await recovery.begin(attempt)
            await recovery.checkpoint_success(
                attempt=attempt,
                normalized_result=result,
                usage_record=complete_usage_record(
                    attempt=attempt,
                    provider_request_id="synthetic-request-0083",
                    input_tokens=20,
                    cached_input_tokens=0,
                    output_tokens=8,
                    latency_ms=Decimal("15.25"),
                    estimated_cost=Decimal("0"),
                ),
            )
            decision = await recovery.recover(attempt)
            assert decision.disposition == "reuse_result"
            assert decision.normalized_result == result

            with pytest.raises(
                AIInvocationRecoveryError, match="domain_finalization_required"
            ):
                await recovery.finalize_cleanup(attempt)

            async with owner.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE jobs SET status='succeeded', "
                        "finished_at=CURRENT_TIMESTAMP WHERE id=:job_id"
                    ),
                    {"job_id": fixture.job_id},
                )
            await recovery.finalize_cleanup(attempt)
            assert (await recovery.recover(attempt)).disposition == "already_finalized"

            async with owner.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT status, normalized_result, normalized_result_hash, "
                            "(SELECT count(*) FROM usage_records "
                            " WHERE provider_attempt_id=:attempt_id) AS usage_count "
                            "FROM ai_invocation_checkpoints "
                            "WHERE provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt.provider_attempt_id},
                    )
                ).mappings().one()
            assert row["status"] == "finalized"
            assert row["normalized_result"] is None
            assert row["normalized_result_hash"] is not None
            assert row["usage_count"] == 1
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(exercise())


def test_usage_and_result_checkpoint_roll_back_together() -> None:
    async def exercise() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            attempt = _attempt(fixture)
            store = PostgresAIInvocationCheckpointStore(worker)
            usage = complete_usage_record(
                attempt=attempt,
                provider_request_id="synthetic-request-rollback",
                input_tokens=1,
                cached_input_tokens=0,
                output_tokens=1,
                latency_ms=Decimal("1"),
                estimated_cost=Decimal("0"),
            )
            await store.begin(attempt)

            with pytest.raises(
                AIInvocationRecoveryError, match="checkpoint_commit_failed"
            ):
                await store.checkpoint_success(
                    attempt=attempt,
                    normalized_result={"sensitive": "must-rollback"},
                    normalized_result_hash="not-a-sha256",
                    usage_record=usage,
                )

            async with owner.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT status, normalized_result, "
                            "(SELECT count(*) FROM usage_records "
                            "WHERE provider_attempt_id=:attempt_id) AS usage_count "
                            "FROM ai_invocation_checkpoints "
                            "WHERE provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt.provider_attempt_id},
                    )
                ).mappings().one()
            assert row["status"] == "started"
            assert row["normalized_result"] is None
            assert row["usage_count"] == 0
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(exercise())


def test_concurrent_redeliveries_create_exactly_one_retry_attempt() -> None:
    async def exercise() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            attempt_zero = _attempt(fixture)
            store = PostgresAIInvocationCheckpointStore(worker)
            recovery = DurableAIInvocationRecovery(store)
            retry_at = datetime(2026, 9, 30, tzinfo=UTC) + timedelta(seconds=1)
            await recovery.begin(attempt_zero)
            await recovery.checkpoint_known_failure(
                attempt=attempt_zero,
                failure_class="timeout",
                retryable=True,
                retry_not_before=retry_at,
                usage_record=unavailable_usage_record(
                    attempt=attempt_zero,
                    failure_class="timeout",
                    latency_ms=Decimal("10"),
                ),
            )
            first_candidate = replace(
                attempt_zero,
                provider_attempt_id=uuid4(),
                retry_no=1,
            )
            second_candidate = replace(
                attempt_zero,
                provider_attempt_id=uuid4(),
                retry_no=1,
            )

            first, second = await asyncio.gather(
                store.begin(first_candidate),
                store.begin(second_candidate),
            )

            assert first.attempt.provider_attempt_id == second.attempt.provider_attempt_id
            async with owner.connect() as connection:
                retry_count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM ai_invocation_checkpoints "
                        "WHERE job_id=:job_id AND retry_no=1"
                    ),
                    {"job_id": fixture.job_id},
                )
            assert retry_count == 1
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(exercise())


def test_ambiguous_attempt_fails_job_without_usage_or_reinvocation() -> None:
    async def exercise() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            attempt = _attempt(fixture)
            recovery = DurableAIInvocationRecovery(
                PostgresAIInvocationCheckpointStore(worker)
            )

            await recovery.begin(attempt)
            first = await recovery.recover(attempt)
            second = await recovery.recover(attempt)
            assert first.disposition == second.disposition == "action_required"

            async with owner.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT checkpoint.status, job.status AS job_status, "
                            "job.error_code, (SELECT count(*) FROM usage_records "
                            "WHERE provider_attempt_id=:attempt_id) AS usage_count "
                            "FROM ai_invocation_checkpoints AS checkpoint "
                            "JOIN jobs AS job ON job.id=checkpoint.job_id "
                            "WHERE checkpoint.provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt.provider_attempt_id},
                    )
                ).mappings().one()
            assert row["status"] == "outcome_unknown"
            assert row["job_status"] == "failed"
            assert row["error_code"] == AI_INVOCATION_OUTCOME_UNKNOWN
            assert row["usage_count"] == 0
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(exercise())


def test_worker_cannot_delete_checkpoint_or_target_another_tenant() -> None:
    async def exercise() -> None:
        owner = _engine()
        worker = _engine(worker=True)
        try:
            fixture = await _seed(owner)
            attempt = _attempt(fixture)
            store = PostgresAIInvocationCheckpointStore(worker)
            await store.begin(attempt)

            with pytest.raises(AIInvocationRecoveryError, match="checkpoint_not_found"):
                await store.begin(
                    replace(
                        attempt,
                        provider_attempt_id=uuid4(),
                        account_id=uuid4(),
                    )
                )
            with pytest.raises(SQLAlchemyError):
                async with owner.begin() as connection:
                    await connection.execute(
                        text(
                            "UPDATE ai_invocation_checkpoints SET task_type='other' "
                            "WHERE provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt.provider_attempt_id},
                    )
            with pytest.raises(SQLAlchemyError):
                async with owner.begin() as connection:
                    await connection.execute(
                        text(
                            "UPDATE ai_invocation_checkpoints "
                            "SET status='finalized', finalized_at=CURRENT_TIMESTAMP "
                            "WHERE provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt.provider_attempt_id},
                    )
            with pytest.raises(SQLAlchemyError):
                async with worker.begin() as connection:
                    await connection.execute(
                        text(
                            "DELETE FROM ai_invocation_checkpoints "
                            "WHERE provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt.provider_attempt_id},
                    )
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(exercise())
