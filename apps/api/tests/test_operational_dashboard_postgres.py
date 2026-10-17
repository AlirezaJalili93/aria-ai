from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.db.runtime import DatabaseRuntime

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)
API_ROOT = Path(__file__).parents[1]


def _migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _execute(sql: str, parameters: dict[str, object] | None = None):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            return await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


async def _execute_as_observer(sql: str):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text("SET LOCAL ROLE aria_observer"))
            return await connection.execute(text(sql))
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def migrate_dashboard_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(_execute("TRUNCATE outbox_events, jobs RESTART IDENTITY CASCADE"))
    yield


def test_observer_has_only_approved_view_access() -> None:
    row = asyncio.run(
        _execute(
            "SELECT "
            "has_table_privilege('aria_observer','public.jobs','SELECT') AS jobs, "
            "has_table_privilege('aria_observer','public.outbox_events','SELECT') AS outbox, "
            "has_table_privilege('aria_observer','public.usage_records','SELECT') AS usage, "
            "has_table_privilege('aria_observer','observability.job_health','SELECT') "
            "AS job_view, "
            "has_table_privilege('aria_observer','observability.outbox_health','SELECT') "
            "AS outbox_view, "
            "has_table_privilege('aria_observer','observability.ai_cost_summary','SELECT') "
            "AS cost_view"
        )
    ).one()
    assert (row.jobs, row.outbox, row.usage) == (False, False, False)
    assert (row.job_view, row.outbox_view, row.cost_view) == (True, True, True)
    grants = asyncio.run(
        _execute(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE table_schema='observability' "
            "AND grantee IN ('anon','authenticated')"
        )
    ).scalar_one()
    assert grants == 0
    assert asyncio.run(
        _execute_as_observer("SELECT queued_count FROM observability.job_health")
    ).scalar_one() == 0
    with pytest.raises(DBAPIError):
        asyncio.run(_execute_as_observer("SELECT count(*) FROM public.jobs"))


def test_queue_count_and_age_come_from_one_postgresql_snapshot() -> None:
    async def scenario() -> None:
        await _execute(
            "INSERT INTO jobs "
            "(id, job_type, status, max_attempts, correlation_id, created_at) "
            "VALUES (:id, 'context_parse', 'queued', 3, :correlation, "
            "CURRENT_TIMESTAMP - INTERVAL '20 seconds')",
            {"id": uuid4(), "correlation": uuid4()},
        )
        row = (await _execute("SELECT * FROM observability.job_health")).one()
        assert row.queued_count == 1
        assert row.oldest_queued_job_age_seconds >= 20

    asyncio.run(scenario())


def test_dashboard_migration_downgrade_and_recovery_preserve_role() -> None:
    command.downgrade(_migration_config(), "0018_scope_versions")
    assert asyncio.run(_execute("SELECT to_regnamespace('observability')")).scalar_one() is None
    assert asyncio.run(
        _execute("SELECT count(*) FROM pg_roles WHERE rolname='aria_observer'")
    ).scalar_one() == 1
    command.upgrade(_migration_config(), "head")
