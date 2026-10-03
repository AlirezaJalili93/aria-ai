from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.db.readiness import normalize_async_database_url

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.db.provision_eval_prices import (  # type: ignore[import-not-found]  # noqa: E402
    FROZEN_PROVIDER_PRICES,
    PriceCatalogProvisioningConflict,
    provision_prices,
    verify_catalog_rows,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _rows() -> tuple[dict[str, object], ...]:
    return tuple(cast(dict[str, object], asdict(price)) for price in FROZEN_PROVIDER_PRICES)


def test_exact_catalog_rows_validate_and_a_changed_rate_fails_closed() -> None:
    rows = _rows()
    verify_catalog_rows(rows)

    conflicting = [dict(row) for row in rows]
    conflicting[0]["output_rate_per_1m"] = "0"
    with pytest.raises(
        PriceCatalogProvisioningConflict,
        match="catalog_rows_missing_or_conflicting",
    ):
        verify_catalog_rows(tuple(conflicting))


@pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for PostgreSQL provisioning evidence",
)
def test_price_provisioning_is_idempotent_in_postgresql() -> None:
    assert TEST_DATABASE_URL is not None

    async def exercise() -> None:
        engine = create_async_engine(
            normalize_async_database_url(TEST_DATABASE_URL),
            poolclass=NullPool,
        )
        try:
            await provision_prices(engine)
            await provision_prices(engine)
            async with engine.connect() as connection:
                count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM provider_price_versions "
                        "WHERE (provider, model, pricing_version) IN "
                        "(('openai','gpt-5.6-terra',"
                        "'openai-gpt-5.6-terra-standard-2026-07-30'),"
                        "('google','gemini-3.8-flash',"
                        "'google-gemini-3.8-flash-standard-intro-2026-09-02'))"
                    )
                )
            assert count == 2
        finally:
            await engine.dispose()

    asyncio.run(exercise())
