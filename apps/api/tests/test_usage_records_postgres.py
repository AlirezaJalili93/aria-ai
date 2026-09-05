from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from decimal import Decimal
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


async def _execute_as_worker(sql: str, parameters: dict[str, object] | None = None) -> None:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text("SET LOCAL ROLE aria_worker"))
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
def clean_usage_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE usage_records, outbox_events, jobs, idempotency_records, "
            "context_source_versions, context_sources, project_create_requests, projects, "
            "account_memberships, profiles, accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_job() -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id, job_id = uuid4(), uuid4(), uuid4(), uuid4()
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
    await _execute(
        "INSERT INTO jobs "
        "(id, account_id, project_id, job_type, max_attempts, correlation_id) "
        "VALUES (:id, :account_id, :project_id, 'context_parse', 3, :correlation_id)",
        {
            "id": job_id,
            "account_id": account_id,
            "project_id": project_id,
            "correlation_id": uuid4(),
        },
    )
    return user_id, account_id, project_id, job_id


def _usage_values(account_id: UUID, project_id: UUID, job_id: UUID) -> dict[str, object]:
    return {
        "account_id": account_id,
        "project_id": project_id,
        "job_id": job_id,
        "task_type": "context_structure",
        "workflow_version": "workflow-v1",
        "prompt_version": "prompt-v1",
        "provider": "provider-recorded-as-data",
        "model": "model-recorded-as-data",
        "provider_request_id": "provider-request-1",
        "input_tokens": 10,
        "cached_input_tokens": 2,
        "output_tokens": 4,
        "latency_ms": Decimal("12.345"),
        "status": "success",
        "error_code": None,
        "retry_no": 0,
        "estimated_cost": Decimal("0.00000001"),
        "pricing_version": "pricing-v1",
        "correlation_id": uuid4(),
    }


USAGE_INSERT = """
INSERT INTO usage_records (
    account_id, project_id, job_id, task_type, workflow_version, prompt_version,
    provider, model, provider_request_id, input_tokens, cached_input_tokens,
    output_tokens, latency_ms, status, error_code, retry_no, estimated_cost,
    pricing_version, correlation_id
) VALUES (
    :account_id, :project_id, :job_id, :task_type, :workflow_version, :prompt_version,
    :provider, :model, :provider_request_id, :input_tokens, :cached_input_tokens,
    :output_tokens, :latency_ms, :status, :error_code, :retry_no, :estimated_cost,
    :pricing_version, :correlation_id
)
"""


def test_m009_usage_schema_matches_the_tightened_contract() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: (
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_columns("usage_records")
                        },
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_indexes("usage_records")
                        },
                        {
                            item["name"]: item.get("options", {}).get("ondelete")
                            for item in inspect(sync_connection).get_foreign_keys("usage_records")
                        },
                    )
                )
        finally:
            await runtime.close()

    columns, indexes, foreign_keys = asyncio.run(inspect_schema())
    assert columns == {
        "id",
        "account_id",
        "project_id",
        "job_id",
        "task_type",
        "workflow_version",
        "prompt_version",
        "provider",
        "model",
        "provider_request_id",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "latency_ms",
        "status",
        "error_code",
        "retry_no",
        "estimated_cost",
        "currency",
        "pricing_version",
        "correlation_id",
        "created_at",
    }
    assert {
        "ix_usage_records_account_created_at",
        "ix_usage_records_project_id",
        "ix_usage_records_job_id",
    }.issubset(indexes)
    assert foreign_keys == {
        "fk_usage_records_account_id_accounts": "RESTRICT",
        "fk_usage_records_project_id_projects": "RESTRICT",
        "fk_usage_records_job_id_jobs": "RESTRICT",
    }
    assert asyncio.run(
        _scalar(
            "SELECT relrowsecurity FROM pg_catalog.pg_class "
            "WHERE oid='public.usage_records'::regclass"
        )
    ) is True


def test_worker_role_is_non_bypass_insert_only_and_data_api_is_denied() -> None:
    role = asyncio.run(
        _scalar(
            "SELECT json_build_object('login', rolcanlogin, 'super', rolsuper, "
            "'bypass', rolbypassrls, "
            "'create_role', rolcreaterole, 'create_db', rolcreatedb) "
            "FROM pg_catalog.pg_roles WHERE rolname='aria_worker'"
        )
    )
    assert role == {
        "login": True,
        "super": False,
        "bypass": False,
        "create_role": False,
        "create_db": False,
    }
    grants = asyncio.run(
        _scalar(
            "SELECT coalesce(json_agg(json_build_object('grantee', grantee, "
            "'privilege', privilege_type) ORDER BY grantee, privilege_type), '[]'::json) "
            "FROM information_schema.role_table_grants WHERE table_schema='public' "
            "AND table_name='usage_records' "
            "AND grantee IN ('aria_worker','aria_api','anon','authenticated')"
        )
    )
    assert grants == [{"grantee": "aria_worker", "privilege": "INSERT"}]
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public' "
            "AND tablename='usage_records' AND cmd='INSERT' "
            "AND roles=ARRAY['aria_worker']::name[]"
        )
    ) == 1


def test_worker_can_append_but_cannot_read_update_or_delete_raw_usage() -> None:
    _, account_id, project_id, job_id = asyncio.run(_seed_job())
    values = _usage_values(account_id, project_id, job_id)
    asyncio.run(_execute_as_worker(USAGE_INSERT, values))
    assert asyncio.run(_scalar("SELECT count(*) FROM usage_records")) == 1

    for statement in (
        "SELECT id FROM usage_records LIMIT 1",
        "UPDATE usage_records SET status='failed'",
        "DELETE FROM usage_records",
    ):
        with pytest.raises(DBAPIError):
            asyncio.run(_execute_as_worker(statement))


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("input_tokens", -1),
        ("cached_input_tokens", -1),
        ("output_tokens", -1),
        ("latency_ms", Decimal("-0.001")),
        ("retry_no", -1),
        ("estimated_cost", Decimal("-0.00000001")),
        ("status", "unknown"),
    ],
)
def test_usage_numeric_and_status_constraints_are_enforced(
    field: str, invalid_value: object
) -> None:
    _, account_id, project_id, job_id = asyncio.run(_seed_job())
    values = _usage_values(account_id, project_id, job_id)
    values[field] = invalid_value
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(USAGE_INSERT, values))


def test_usage_records_are_immutable_and_parent_hard_delete_is_restricted() -> None:
    _, account_id, project_id, job_id = asyncio.run(_seed_job())
    asyncio.run(_execute(USAGE_INSERT, _usage_values(account_id, project_id, job_id)))

    for statement in (
        "UPDATE usage_records SET status='failed'",
        "DELETE FROM usage_records",
    ):
        with pytest.raises(DBAPIError):
            asyncio.run(_execute(statement))

    for statement, parameters in (
        ("DELETE FROM jobs WHERE id=:id", {"id": job_id}),
        ("DELETE FROM projects WHERE id=:id", {"id": project_id}),
        ("DELETE FROM accounts WHERE id=:id", {"id": account_id}),
    ):
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(statement, parameters))


def test_m009_downgrade_reupgrade_removes_ledger_authority_safely() -> None:
    config = _migration_config()
    command.downgrade(config, "0006_idempotency_records")
    assert not asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='usage_records')"
        )
    )
    assert asyncio.run(
        _scalar("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aria_worker')")
    ) is True
    command.upgrade(config, "head")
    assert asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='usage_records')"
        )
    ) is True
