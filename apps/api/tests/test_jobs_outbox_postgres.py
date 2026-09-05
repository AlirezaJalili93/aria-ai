from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
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


async def _scalar(sql: str, parameters: dict[str, object] | None = None) -> object:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.connect() as connection:
            return (await connection.execute(text(sql), parameters or {})).scalar_one()
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_jobs_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE outbox_events, jobs, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_project() -> tuple[UUID, UUID, UUID]:
    user_id, account_id, project_id = uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:user_id)", {"user_id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:account_id)", {"account_id": account_id})
    await _execute(
        "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
        "VALUES (:id, :account_id, :user_id, 'owner', 'active')",
        {"id": uuid4(), "account_id": account_id, "user_id": user_id},
    )
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account_id, :user_id, 'Project', 'landing')",
        {"id": project_id, "account_id": account_id, "user_id": user_id},
    )
    return user_id, account_id, project_id


def test_m008_schema_uses_current_dictionary_fields_indexes_rls_and_fks() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                columns, indexes, foreign_keys = await connection.run_sync(
                    lambda sync_connection: (
                        {
                            table: {
                                item["name"]
                                for item in inspect(sync_connection).get_columns(table)
                            }
                            for table in ("jobs", "outbox_events")
                        },
                        {
                            item["name"]
                            for table in ("jobs", "outbox_events")
                            for item in inspect(sync_connection).get_indexes(table)
                        },
                        {
                            item["name"]
                            for table in ("jobs", "outbox_events")
                            for item in inspect(sync_connection).get_foreign_keys(table)
                        },
                    )
                )
                rls_rows = (
                    await connection.execute(
                        text(
                            "SELECT relname, relrowsecurity FROM pg_catalog.pg_class "
                            "WHERE oid IN ('public.jobs'::regclass, "
                            "'public.outbox_events'::regclass)"
                        )
                    )
                ).all()
                return columns, indexes, foreign_keys, {
                    str(row[0]): bool(row[1]) for row in rls_rows
                }
        finally:
            await runtime.close()

    columns, indexes, foreign_keys, rls = asyncio.run(inspect_schema())
    assert columns["jobs"] == {
        "id",
        "account_id",
        "project_id",
        "job_type",
        "status",
        "payload_ref",
        "attempt_count",
        "max_attempts",
        "idempotency_key",
        "correlation_id",
        "available_at",
        "started_at",
        "finished_at",
        "error_code",
        "error_detail",
        "created_at",
    }
    assert columns["outbox_events"] == {
        "id",
        "account_id",
        "aggregate_type",
        "aggregate_id",
        "event_type",
        "payload",
        "status",
        "attempt_count",
        "available_at",
        "created_at",
        "published_at",
    }
    assert {
        "ix_jobs_status_available_at",
        "ix_jobs_account_project_created_at",
        "ix_outbox_events_status_available_at",
        "ix_outbox_events_account_created_at",
    }.issubset(indexes)
    assert {
        "fk_jobs_account_id_accounts",
        "fk_jobs_project_account_projects",
        "fk_outbox_events_account_id_accounts",
    }.issubset(foreign_keys)
    assert rls == {"jobs": True, "outbox_events": True}


def test_job_constraints_and_cross_tenant_project_linkage_are_enforced() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    _, other_account_id, _ = asyncio.run(_seed_project())
    base = {
        "id": uuid4(),
        "account_id": account_id,
        "project_id": project_id,
        "correlation_id": uuid4(),
    }
    asyncio.run(
        _execute(
            "INSERT INTO jobs "
            "(id, account_id, project_id, job_type, max_attempts, correlation_id) "
            "VALUES (:id, :account_id, :project_id, 'context_parse', 3, :correlation_id)",
            base,
        )
    )
    for sql, parameters in (
        (
            "INSERT INTO jobs "
            "(id, account_id, project_id, job_type, status, max_attempts, correlation_id) "
            "VALUES (:id, :account_id, :project_id, 'context_parse', 'unknown', 3, "
            ":correlation_id)",
            {**base, "id": uuid4()},
        ),
        (
            "INSERT INTO jobs "
            "(id, account_id, project_id, job_type, attempt_count, max_attempts, "
            "correlation_id) VALUES (:id, :account_id, :project_id, 'context_parse', "
            "4, 3, :correlation_id)",
            {**base, "id": uuid4()},
        ),
        (
            "INSERT INTO jobs "
            "(id, account_id, project_id, job_type, max_attempts, correlation_id) "
            "VALUES (:id, :account_id, :project_id, 'context_parse', 3, :correlation_id)",
            {**base, "id": uuid4(), "account_id": other_account_id},
        ),
    ):
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(sql, parameters))


def test_job_and_outbox_commit_atomically_and_outbox_payload_is_immutable() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    job_id, outbox_id, aggregate_id = uuid4(), uuid4(), uuid4()

    async def transaction() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO jobs "
                        "(id, account_id, project_id, job_type, max_attempts, correlation_id) "
                        "VALUES (:job_id, :account_id, :project_id, 'context_parse', 3, "
                        ":correlation_id)"
                    ),
                    {
                        "job_id": job_id,
                        "account_id": account_id,
                        "project_id": project_id,
                        "correlation_id": uuid4(),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO outbox_events "
                        "(id, account_id, aggregate_type, aggregate_id, event_type, payload) "
                        "VALUES (:id, :account_id, 'context_source', :aggregate_id, "
                        "'context_added.v1', CAST(:payload AS jsonb))"
                    ),
                    {
                        "id": outbox_id,
                        "account_id": account_id,
                        "aggregate_id": aggregate_id,
                        "payload": '{"payloadVersion":"1"}',
                    },
                )
        finally:
            await runtime.close()

    asyncio.run(transaction())
    assert int(asyncio.run(_scalar("SELECT count(*) FROM jobs WHERE id=:id", {"id": job_id}))) == 1
    assert (
        int(
            asyncio.run(
                _scalar("SELECT count(*) FROM outbox_events WHERE id=:id", {"id": outbox_id})
            )
        )
        == 1
    )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE outbox_events SET payload='{}'::jsonb WHERE id=:id",
                {"id": outbox_id},
            )
        )

    rollback_job_id = uuid4()

    async def failing_transaction() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO jobs "
                        "(id, account_id, project_id, job_type, max_attempts, correlation_id) "
                        "VALUES (:job_id, :account_id, :project_id, 'context_parse', 3, "
                        ":correlation_id)"
                    ),
                    {
                        "job_id": rollback_job_id,
                        "account_id": account_id,
                        "project_id": project_id,
                        "correlation_id": uuid4(),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO outbox_events "
                        "(account_id, aggregate_type, aggregate_id, event_type, payload, status) "
                        "VALUES (:account_id, 'context_source', :aggregate_id, "
                        "'context_added.v1', '{}'::jsonb, 'invalid')"
                    ),
                    {"account_id": account_id, "aggregate_id": aggregate_id},
                )
        finally:
            await runtime.close()

    with pytest.raises(IntegrityError):
        asyncio.run(failing_transaction())
    assert (
        int(
            asyncio.run(
                _scalar("SELECT count(*) FROM jobs WHERE id=:id", {"id": rollback_job_id})
            )
        )
        == 0
    )


def test_m008_has_no_data_api_grants_and_downgrade_reupgrade_is_safe() -> None:
    assert (
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='public' AND table_name IN ('jobs','outbox_events') "
                "AND grantee IN ('anon','authenticated')"
            )
        )
        == 0
    )
    config = _migration_config()
    command.downgrade(config, "0004_context_sources")
    assert not asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='jobs')"
        )
    )
    command.upgrade(config, "head")
    assert asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='outbox_events')"
        )
    )
