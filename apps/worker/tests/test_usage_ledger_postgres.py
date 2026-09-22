from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from aria_observability import NoOpOperationalMetrics
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.usage_ledger import UsageRecord
from app.infrastructure.db.usage_ledger import SqlAlchemyUsageLedger

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


class CountingMetrics(NoOpOperationalMetrics):
    def __init__(self) -> None:
        self.ai_usage_calls = 0

    def record_ai_usage(
        self,
        *,
        workflow: str,
        provider: str,
        model: str,
        status: str,
        latency_ms: float,
        task_type: str,
        estimated_cost: float,
        currency: str,
    ) -> None:
        del workflow, provider, model, status, latency_ms
        del task_type, estimated_cost, currency
        self.ai_usage_calls += 1


def test_same_provider_attempt_persistence_is_idempotent() -> None:
    assert TEST_DATABASE_URL is not None

    async def exercise() -> None:
        engine = create_async_engine(TEST_DATABASE_URL)
        account_id = uuid4()
        attempt_id = uuid4()
        correlation_id = uuid4()
        identity_suffix = uuid4().hex
        provider = f"synthetic-{identity_suffix}"
        model = f"synthetic-model-{identity_suffix}"
        pricing_version = f"price-{identity_suffix}"
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("INSERT INTO accounts (id) VALUES (:account_id)"),
                    {"account_id": account_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO provider_price_versions "
                        "(provider, model, pricing_version, currency, input_rate_per_1m, "
                        "cached_input_rate_per_1m, output_rate_per_1m, effective_from) "
                        "VALUES (:provider, :model, :pricing_version, 'USD', "
                        "1, 1, 1, :effective_from)"
                    ),
                    {
                        "provider": provider,
                        "model": model,
                        "pricing_version": pricing_version,
                        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
                    },
                )

            record = UsageRecord(
                account_id=account_id,
                provider_attempt_id=attempt_id,
                project_id=None,
                job_id=None,
                task_type="synthetic-task",
                workflow_version="workflow-v1",
                prompt_version="prompt-v1",
                provider=provider,
                model=model,
                provider_request_id="request-v1",
                input_tokens=10,
                cached_input_tokens=0,
                output_tokens=5,
                latency_ms=Decimal("10"),
                status="success",
                error_code=None,
                retry_no=0,
                repair_no=0,
                estimated_cost=Decimal("0.00001500"),
                pricing_version=pricing_version,
                correlation_id=correlation_id,
            )
            metrics = CountingMetrics()
            ledger = SqlAlchemyUsageLedger(engine, metrics)
            await ledger.append(record)
            await ledger.append(record)

            async with engine.connect() as connection:
                count = (
                    await connection.execute(
                        text(
                            "SELECT count(*) FROM usage_records "
                            "WHERE provider_attempt_id=:attempt_id"
                        ),
                        {"attempt_id": attempt_id},
                    )
                ).scalar_one()
            assert count == 1
            assert metrics.ai_usage_calls == 1
        finally:
            await engine.dispose()

    asyncio.run(exercise())
