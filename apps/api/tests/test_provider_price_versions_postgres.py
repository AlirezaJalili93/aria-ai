from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.infrastructure.db.runtime import DatabaseRuntime

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)
API_ROOT = Path(__file__).parents[1]


def _migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _execute(sql: str, parameters: dict[str, object] | None = None) -> None:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


async def _execute_as_worker(sql: str) -> None:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text("SET LOCAL ROLE aria_worker"))
            await connection.execute(text(sql))
    finally:
        await runtime.close()


async def _scalar(sql: str, parameters: dict[str, object] | None = None) -> object:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.connect() as connection:
            return (await connection.execute(text(sql), parameters or {})).scalar_one()
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_price_catalog() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(_execute("TRUNCATE usage_records, provider_price_versions CASCADE"))
    yield


def _insert_price(
    *, pricing_version: str, effective_from: datetime, input_rate: str = "2.00000000"
) -> None:
    asyncio.run(
        _execute(
            "INSERT INTO provider_price_versions "
            "(provider, model, pricing_version, currency, input_rate_per_1m, "
            "cached_input_rate_per_1m, output_rate_per_1m, effective_from) VALUES "
            "('synthetic-provider', 'synthetic-model', :version, 'USD', :input_rate, "
            "'0.50000000', '8.00000000', :effective_from)",
            {
                "version": pricing_version,
                "input_rate": Decimal(input_rate),
                "effective_from": effective_from,
            },
        )
    )


def test_catalog_is_empty_by_default_and_worker_has_read_only_access() -> None:
    assert asyncio.run(_scalar("SELECT count(*) FROM provider_price_versions")) == 0
    grants = asyncio.run(
        _scalar(
            "SELECT coalesce(json_agg(privilege_type ORDER BY privilege_type), '[]'::json) "
            "FROM information_schema.role_table_grants WHERE table_schema='public' "
            "AND table_name='provider_price_versions' AND grantee='aria_worker'"
        )
    )
    assert grants == ["SELECT"]
    asyncio.run(_execute_as_worker("SELECT count(*) FROM provider_price_versions"))
    for statement in (
        "INSERT INTO provider_price_versions "
        "(provider, model, pricing_version, currency, input_rate_per_1m, "
        "cached_input_rate_per_1m, output_rate_per_1m, effective_from) "
        "VALUES ('x','y','z','USD',0,0,0,now())",
        "UPDATE provider_price_versions SET currency='EUR'",
        "DELETE FROM provider_price_versions",
    ):
        with pytest.raises(DBAPIError):
            asyncio.run(_execute_as_worker(statement))


def test_catalog_versions_are_unique_non_negative_and_immutable() -> None:
    _insert_price(
        pricing_version="v1", effective_from=datetime(2026, 1, 1, tzinfo=UTC)
    )
    for statement in (
        "UPDATE provider_price_versions SET input_rate_per_1m=3",
        "DELETE FROM provider_price_versions",
    ):
        with pytest.raises(DBAPIError):
            asyncio.run(_execute(statement))

    with pytest.raises(IntegrityError):
        _insert_price(
            pricing_version="v1", effective_from=datetime(2026, 2, 1, tzinfo=UTC)
        )
    with pytest.raises(IntegrityError):
        _insert_price(
            pricing_version="v2", effective_from=datetime(2026, 1, 1, tzinfo=UTC)
        )
    with pytest.raises(IntegrityError):
        _insert_price(
            pricing_version="v-negative",
            effective_from=datetime(2026, 3, 1, tzinfo=UTC),
            input_rate="-0.00000001",
        )


def test_effective_price_query_is_latest_at_or_before_execution_time() -> None:
    _insert_price(
        pricing_version="v1", effective_from=datetime(2026, 1, 1, tzinfo=UTC)
    )
    _insert_price(
        pricing_version="v2", effective_from=datetime(2026, 2, 1, tzinfo=UTC)
    )
    assert TEST_DATABASE_URL is not None

    resolved = asyncio.run(
        _scalar(
            "SELECT pricing_version FROM provider_price_versions "
            "WHERE provider=:provider AND model=:model "
            "AND effective_from <= :provider_execution_at "
            "ORDER BY effective_from DESC LIMIT 1",
            {
                "provider": "synthetic-provider",
                "model": "synthetic-model",
                "provider_execution_at": datetime(2026, 2, 15, tzinfo=UTC),
            },
        )
    )
    assert resolved == "v2"


def test_upgrade_preserves_historical_usage_but_new_rows_require_catalog_match() -> None:
    config = _migration_config()
    command.downgrade(config, "0022_context_source_management")
    account_id = uuid4()
    asyncio.run(
        _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    )
    legacy_insert = (
        "INSERT INTO usage_records "
        "(account_id, task_type, workflow_version, prompt_version, provider, model, "
        "input_tokens, cached_input_tokens, output_tokens, latency_ms, status, retry_no, "
        "repair_no, estimated_cost, currency, pricing_version, correlation_id) VALUES "
        "(:account_id, 'synthetic-task', 'workflow-v1', 'prompt-v1', "
        "'legacy-provider', 'legacy-model', 1, 0, 0, 1, 'success', 0, 0, 0, 'USD', "
        "'legacy-price', :correlation_id)"
    )
    asyncio.run(
        _execute(
            legacy_insert,
            {"account_id": account_id, "correlation_id": uuid4()},
        )
    )

    command.upgrade(config, "head")

    assert asyncio.run(_scalar("SELECT count(*) FROM usage_records")) == 1
    validation = asyncio.run(
        _scalar(
            "SELECT json_object_agg(conname, convalidated) FROM pg_constraint "
            "WHERE conname IN ('fk_usage_records_provider_price', "
            "'usage_cached_input_subset')"
        )
    )
    assert validation == {
        "fk_usage_records_provider_price": False,
        "usage_cached_input_subset": False,
    }
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                legacy_insert,
                {"account_id": account_id, "correlation_id": uuid4()},
            )
        )
