from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from aria_observability import NoOpOperationalMetrics
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.provider_adapter import ProviderResult
from app.application.provider_execution import ProviderCandidate
from app.application.provider_failure_policy import ProviderExecutionMetadata
from app.application.provider_quality_evaluation import (
    ControlledProviderQualityEvaluation,
    EvaluationCase,
)
from app.application.usage_ledger import UsageRecord
from app.infrastructure.ai.provider_quality_fixtures import load_versioned_synthetic_cases
from app.infrastructure.ai.provider_quality_prompt_package import (
    ApprovedPromptSchemaPackageV1,
)
from app.infrastructure.db.provider_pricing import PostgresProviderPriceCatalog
from app.infrastructure.db.usage_ledger import SqlAlchemyUsageLedger

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL preflight evidence",
)


class NoProviderCall:
    async def execute(self, request: object) -> ProviderResult:
        del request
        raise AssertionError("PostgreSQL preflight must make zero Provider calls")


class LocalModelIdentityPreflight:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def verify(self, *, provider: str, model: str) -> None:
        self.calls.append((provider, model))


class NoInvocation:
    async def execute(
        self,
        *,
        candidate: ProviderCandidate,
        request: object,
        metadata: ProviderExecutionMetadata,
        pinned_price: object,
    ) -> object:
        del candidate, request, metadata, pinned_price
        raise AssertionError("preflight must make zero Provider calls")


def _engine(*, worker: bool = False) -> AsyncEngine:
    assert TEST_DATABASE_URL is not None
    connect_args = {"server_settings": {"role": "aria_worker"}} if worker else {}
    return create_async_engine(
        TEST_DATABASE_URL,
        connect_args=connect_args,
        poolclass=NullPool,
    )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _cases() -> tuple[ApprovedPromptSchemaPackageV1, tuple[EvaluationCase, ...]]:
    package = ApprovedPromptSchemaPackageV1()
    return package, load_versioned_synthetic_cases(
        repository_root=_repository_root(), request_factory=package
    )


def test_postgres_price_and_worker_ledger_preflight_for_approved_candidates() -> None:
    assert TEST_DATABASE_URL is not None

    async def exercise() -> None:
        admin_engine = _engine()
        worker_engine = _engine(worker=True)
        account_id = uuid4()
        suffix = uuid4().hex
        openai_price = f"openai-eval-{suffix}"
        gemini_price = f"gemini-eval-{suffix}"
        execution_at = datetime(
            2099,
            1,
            1,
            microsecond=int(suffix[:5], 16),
            tzinfo=UTC,
        )
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(
                    text("INSERT INTO accounts (id) VALUES (:account_id)"),
                    {"account_id": account_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO provider_price_versions "
                        "(provider, model, pricing_version, currency, input_rate_per_1m, "
                        "cached_input_rate_per_1m, output_rate_per_1m, effective_from) VALUES "
                        "('openai','gpt-5.6-terra',:openai_price,'USD',2,0.2,12,:at), "
                        "('google','gemini-3.8-flash',:gemini_price,'USD',0.75,0.075,3.75,:at)"
                    ),
                    {
                        "openai_price": openai_price,
                        "gemini_price": gemini_price,
                        "at": execution_at,
                    },
                )

            package, cases = _cases()
            model_preflight = LocalModelIdentityPreflight()
            catalog = PostgresProviderPriceCatalog(worker_engine)
            harness = ControlledProviderQualityEvaluation(
                price_catalog=catalog,
                model_preflight=model_preflight,
                invocation=NoInvocation(),  # type: ignore[arg-type]
                output_normalizer=package,
            )
            candidates = (
                ProviderCandidate("openai", "gpt-5.6-terra", NoProviderCall()),
                ProviderCandidate("google", "gemini-3.8-flash", NoProviderCall()),
            )
            preflight = await harness.preflight(
                cases=cases,
                candidates=candidates,
                execution_at=execution_at,
                paid_synthetic_evaluation_confirmed=True,
            )

            assert preflight.planned_invocations == 120
            assert preflight.maximum_reserved_cost == Decimal("24.94500000")
            assert [value.price.pricing_version for value in preflight.candidates] == [
                openai_price,
                gemini_price,
            ]
            assert model_preflight.calls == [
                ("openai", "gpt-5.6-terra"),
                ("google", "gemini-3.8-flash"),
            ]

            ledger = SqlAlchemyUsageLedger(worker_engine, NoOpOperationalMetrics())
            attempt_id = uuid4()
            await ledger.append(
                UsageRecord(
                    account_id=account_id,
                    provider_attempt_id=attempt_id,
                    project_id=None,
                    job_id=None,
                    task_type="controlled_real_provider_eval",
                    workflow_version="ai-01-context-structuring-v1",
                    prompt_version="ai-01-real-eval-prompt-v1",
                    provider="openai",
                    model="gpt-5.6-terra",
                    provider_request_id="synthetic-preflight-only",
                    input_tokens=1,
                    cached_input_tokens=0,
                    output_tokens=1,
                    latency_ms=Decimal("1"),
                    status="success",
                    error_code=None,
                    retry_no=0,
                    repair_no=0,
                    estimated_cost=Decimal("0.00001400"),
                    pricing_version=openai_price,
                    correlation_id=uuid4(),
                )
            )
            async with admin_engine.connect() as connection:
                count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM usage_records WHERE provider_attempt_id=:attempt_id"
                    ),
                    {"attempt_id": attempt_id},
                )
            assert count == 1
        finally:
            # The ledger is append-only by contract. This test runs only against an
            # isolated throwaway database, so its synthetic evidence is not deleted.
            await worker_engine.dispose()
            await admin_engine.dispose()

    asyncio.run(exercise())
