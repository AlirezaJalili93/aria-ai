from __future__ import annotations

import asyncio
import os
import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.provider_pricing import ProviderPriceNotFoundError
from app.infrastructure.db.provider_pricing import PostgresProviderPriceCatalog

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


def _engine() -> AsyncEngine:
    assert TEST_DATABASE_URL is not None
    if TEST_DATABASE_URL.startswith("postgresql+asyncpg://"):
        value = TEST_DATABASE_URL
    elif TEST_DATABASE_URL.startswith("postgres://"):
        value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        value = TEST_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    return create_async_engine(re.sub(r"([?&])sslmode=", r"\1ssl=", value), poolclass=NullPool)


def test_postgres_catalog_resolves_the_latest_effective_version() -> None:
    async def exercise() -> None:
        engine = _engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("TRUNCATE usage_records, provider_price_versions CASCADE")
                )
                await connection.execute(
                    text(
                        "INSERT INTO provider_price_versions "
                        "(provider, model, pricing_version, currency, input_rate_per_1m, "
                        "cached_input_rate_per_1m, output_rate_per_1m, effective_from) VALUES "
                        "('synthetic-provider','synthetic-model','v1','USD',1,0.5,8,"
                        "'2026-01-01T00:00:00Z'), "
                        "('synthetic-provider','synthetic-model','v2','USD',2,0.5,8,"
                        "'2026-02-01T00:00:00Z')"
                    )
                )
            catalog = PostgresProviderPriceCatalog(engine)
            price = await catalog.resolve(
                provider="synthetic-provider",
                model="synthetic-model",
                provider_execution_at=datetime(2026, 2, 15, tzinfo=UTC),
            )
            assert price.pricing_version == "v2"
            with pytest.raises(ProviderPriceNotFoundError):
                await catalog.resolve(
                    provider="unpriced-provider",
                    model="unpriced-model",
                    provider_execution_at=datetime(2026, 2, 15, tzinfo=UTC),
                )
        finally:
            await engine.dispose()

    asyncio.run(exercise())
