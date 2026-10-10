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
from app.modules.context.infrastructure.management_repository import (
    SqlAlchemyContextSourceManagementUnitOfWorkFactory,
)
from app.modules.context.infrastructure.repository import SqlAlchemyContextSourceRepository

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
def clean_context_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE context_source_versions, context_sources, project_create_requests, "
            "projects, account_memberships, profiles, accounts RESTART IDENTITY CASCADE"
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


async def _seed_source() -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id = await _seed_project()
    source_id = uuid4()
    await _execute(
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, raw_text, created_by) "
        "VALUES (:id, :account_id, :project_id, 'text', 'uploaded', 'private', :user_id)",
        {
            "id": source_id,
            "account_id": account_id,
            "project_id": project_id,
            "user_id": user_id,
        },
    )
    return user_id, account_id, project_id, source_id


def test_m003_schema_has_exact_fields_tenant_indexes_rls_and_foreign_keys() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema() -> tuple[set[str], set[str], set[str], set[str], bool, bool]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                source_columns, version_columns, indexes, foreign_keys = await connection.run_sync(
                    lambda sync_connection: (
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_columns("context_sources")
                        },
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_columns(
                                "context_source_versions"
                            )
                        },
                        {
                            item["name"]
                            for table in ("context_sources", "context_source_versions")
                            for item in inspect(sync_connection).get_indexes(table)
                        },
                        {
                            item["name"]
                            for table in ("context_sources", "context_source_versions")
                            for item in inspect(sync_connection).get_foreign_keys(table)
                        },
                    )
                )
                rls_rows = (
                    await connection.execute(
                        text(
                            "SELECT relname, relrowsecurity FROM pg_catalog.pg_class "
                            "WHERE oid IN ('public.context_sources'::regclass, "
                            "'public.context_source_versions'::regclass)"
                        )
                    )
                ).all()
                rls = {str(row[0]): bool(row[1]) for row in rls_rows}
                return (
                    source_columns,
                    version_columns,
                    indexes,
                    foreign_keys,
                    rls["context_sources"],
                    rls["context_source_versions"],
                )
        finally:
            await runtime.close()

    source_columns, version_columns, indexes, foreign_keys, source_rls, version_rls = asyncio.run(
        inspect_schema()
    )
    assert source_columns == {
        "id",
        "account_id",
        "project_id",
        "source_type",
        "status",
        "original_name",
        "mime_type",
        "storage_ref",
        "raw_text",
        "checksum",
        "created_by",
        "created_at",
        "updated_at",
    }
    assert version_columns == {
        "id",
        "account_id",
        "project_id",
        "source_id",
        "version_no",
        "content_hash",
        "canonical_text",
        "storage_ref",
        "metadata",
        "parse_status",
        "created_at",
    }
    assert {
        "ix_context_sources_account_id_project_id_created_at",
        "ix_context_versions_tenant_source_status_no",
    }.issubset(indexes)
    assert {
        "fk_context_sources_account_id_accounts",
        "fk_context_sources_project_id_account_id_projects",
        "fk_context_sources_created_by_profiles",
        "fk_context_source_versions_source_tenant",
    }.issubset(foreign_keys)
    assert source_rls and version_rls


def test_management_projection_selects_latest_and_ready_versions_without_content() -> None:
    user_id, account_id, project_id, source_id = asyncio.run(_seed_source())
    ready_version_id, failed_version_id, failed_job_id = uuid4(), uuid4(), uuid4()
    asyncio.run(
        _execute(
            "UPDATE context_sources SET status='failed', storage_ref='private/object' "
            "WHERE id=:id",
            {"id": source_id},
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO context_source_versions "
            "(id, account_id, project_id, source_id, version_no, canonical_text, "
            "parse_status) VALUES (:id, :account_id, :project_id, :source_id, 1, "
            "'customer text', 'ready')",
            {
                "id": ready_version_id,
                "account_id": account_id,
                "project_id": project_id,
                "source_id": source_id,
            },
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO context_source_versions "
            "(id, account_id, project_id, source_id, version_no, storage_ref, parse_status) "
            "VALUES (:id, :account_id, :project_id, :source_id, 2, 'private/object', 'failed')",
            {
                "id": failed_version_id,
                "account_id": account_id,
                "project_id": project_id,
                "source_id": source_id,
            },
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO jobs "
            "(id, account_id, project_id, job_type, status, payload_ref, max_attempts, "
            "correlation_id, error_code) VALUES (:id, :account_id, :project_id, "
            "'context_source_parse', 'failed', CAST(:payload AS jsonb), 1, "
            ":correlation_id, 'PARSER_STORAGE_UNAVAILABLE')",
            {
                "id": failed_job_id,
                "account_id": account_id,
                "project_id": project_id,
                "payload": (
                    f'{{"source_id":"{source_id}",'
                    f'"source_version_id":"{failed_version_id}"}}'
                ),
                "correlation_id": uuid4(),
            },
        )
    )

    async def scenario():
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            factory = SqlAlchemyContextSourceManagementUnitOfWorkFactory(
                runtime.session_factory
            )
            async with factory() as unit_of_work:
                rows = await unit_of_work.repository.list_sources(
                    account_id=account_id,
                    project_id=project_id,
                    limit=20,
                    cursor_created_at=None,
                    cursor_id=None,
                )
                assert len(rows) == 1
                row = rows[0]
                assert row.latest_version is not None
                assert row.latest_version.id == failed_version_id
                assert row.current_ready_version is not None
                assert row.current_ready_version.id == ready_version_id
                assert row.latest_job is not None
                assert row.latest_job.id == failed_job_id
                assert row.latest_job.retryable is True
                assert not hasattr(row, "storage_ref")
                assert not hasattr(row.latest_version, "canonical_text")
                assert await unit_of_work.repository.archive_source(
                    account_id=account_id,
                    project_id=project_id,
                    source_id=source_id,
                )
                await unit_of_work.commit()
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert asyncio.run(
        _scalar("SELECT status FROM context_sources WHERE id=:id", {"id": source_id})
    ) == "deleted"
    assert int(
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM context_source_versions WHERE source_id=:id",
                {"id": source_id},
            )
        )
    ) == 2
    assert asyncio.run(
        _scalar("SELECT storage_ref FROM context_sources WHERE id=:id", {"id": source_id})
    ) == "private/object"


def test_database_rejects_invalid_vocabularies_version_and_ready_without_content() -> None:
    user_id, account_id, project_id, source_id = asyncio.run(_seed_source())
    source_sql = (
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, created_by) "
        "VALUES (:id, :account_id, :project_id, :source_type, :status, :user_id)"
    )
    for source_type, status in (("voice", "uploaded"), ("text", "processing")):
        with pytest.raises(IntegrityError):
            asyncio.run(
                _execute(
                    source_sql,
                    {
                        "id": uuid4(),
                        "account_id": account_id,
                        "project_id": project_id,
                        "source_type": source_type,
                        "status": status,
                        "user_id": user_id,
                    },
                )
            )

    version_sql = (
        "INSERT INTO context_source_versions "
        "(id, account_id, project_id, source_id, version_no, parse_status) "
        "VALUES (:id, :account_id, :project_id, :source_id, :version_no, :parse_status)"
    )
    for version_no, parse_status in ((0, "pending"), (1, "uploaded"), (1, "ready")):
        with pytest.raises(IntegrityError):
            asyncio.run(
                _execute(
                    version_sql,
                    {
                        "id": uuid4(),
                        "account_id": account_id,
                        "project_id": project_id,
                        "source_id": source_id,
                        "version_no": version_no,
                        "parse_status": parse_status,
                    },
                )
            )

    valid_version = {
        "id": uuid4(),
        "account_id": account_id,
        "project_id": project_id,
        "source_id": source_id,
        "version_no": 1,
        "parse_status": "pending",
    }
    asyncio.run(_execute(version_sql, valid_version))
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(version_sql, {**valid_version, "id": uuid4()}))


def test_composite_foreign_keys_reject_cross_tenant_linkage_and_missing_creator() -> None:
    user_a, account_a, project_a = asyncio.run(_seed_project())
    _, account_b, project_b = asyncio.run(_seed_project())
    source_id = uuid4()
    source_sql = (
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, created_by) "
        "VALUES (:id, :account_id, :project_id, 'text', 'uploaded', :created_by)"
    )
    for project_id, created_by in ((project_b, user_a), (project_a, uuid4())):
        with pytest.raises(IntegrityError):
            asyncio.run(
                _execute(
                    source_sql,
                    {
                        "id": uuid4(),
                        "account_id": account_a,
                        "project_id": project_id,
                        "created_by": created_by,
                    },
                )
            )
    asyncio.run(
        _execute(
            source_sql,
            {
                "id": source_id,
                "account_id": account_a,
                "project_id": project_a,
                "created_by": user_a,
            },
        )
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                "INSERT INTO context_source_versions "
                "(id, account_id, project_id, source_id, version_no, parse_status) "
                "VALUES (:id, :account_id, :project_id, :source_id, 1, 'pending')",
                {
                    "id": uuid4(),
                    "account_id": account_b,
                    "project_id": project_b,
                    "source_id": source_id,
                },
            )
        )


def test_ready_version_is_immutable_and_hard_source_delete_is_restricted() -> None:
    _, account_id, project_id, source_id = asyncio.run(_seed_source())
    version_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO context_source_versions "
            "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
            "VALUES (:id, :account_id, :project_id, :source_id, 1, 'canonical', 'ready')",
            {
                "id": version_id,
                "account_id": account_id,
                "project_id": project_id,
                "source_id": source_id,
            },
        )
    )
    for statement in (
        "UPDATE context_source_versions SET canonical_text='changed' WHERE id=:id",
        "UPDATE context_source_versions SET metadata='{}'::jsonb WHERE id=:id",
        "UPDATE context_source_versions SET parse_status='failed' WHERE id=:id",
    ):
        with pytest.raises(DBAPIError) as error:
            asyncio.run(_execute(statement, {"id": version_id}))
        assert getattr(error.value.orig, "sqlstate", None) == "55000"
    with pytest.raises(IntegrityError):
        asyncio.run(_execute("DELETE FROM context_sources WHERE id=:id", {"id": source_id}))


def test_repository_derives_current_ready_version_and_excludes_deleted_source() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> tuple[int | None, bool, bool, int]:
        _, account_id, project_id, source_id = await _seed_source()
        for version_no, parse_status, canonical_text in (
            (1, "ready", "one"),
            (2, "ready", "two"),
            (3, "failed", None),
        ):
            await _execute(
                "INSERT INTO context_source_versions "
                "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
                "VALUES (:id, :account_id, :project_id, :source_id, :version_no, "
                ":canonical_text, :parse_status)",
                {
                    "id": uuid4(),
                    "account_id": account_id,
                    "project_id": project_id,
                    "source_id": source_id,
                    "version_no": version_no,
                    "canonical_text": canonical_text,
                    "parse_status": parse_status,
                },
            )
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.session_factory() as session:
                repository = SqlAlchemyContextSourceRepository(session)
                current = await repository.get_current_ready_version(
                    account_id=account_id, project_id=project_id, source_id=source_id
                )
                await repository.set_source_status(
                    account_id=account_id,
                    project_id=project_id,
                    source_id=source_id,
                    status="deleted",
                )
                await session.commit()
                visible = await repository.get_source(
                    account_id=account_id, project_id=project_id, source_id=source_id
                )
                hidden_current = await repository.get_current_ready_version(
                    account_id=account_id, project_id=project_id, source_id=source_id
                )
            count = int(
                await _scalar(
                    "SELECT count(*) FROM context_source_versions WHERE source_id=:source_id",
                    {"source_id": source_id},
                )
            )
            return (
                current.version_no if current else None,
                visible is None,
                hidden_current is None,
                count,
            )
        finally:
            await runtime.close()

    current_version, hidden, current_hidden, version_count = asyncio.run(scenario())
    assert current_version == 2
    assert hidden
    assert current_hidden
    assert version_count == 3


def test_m003_has_no_data_api_grants_and_downgrade_reupgrade_is_safe() -> None:
    assert (
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='public' "
                "AND table_name IN ('context_sources','context_source_versions') "
                "AND grantee IN ('anon','authenticated')"
            )
        )
        == 0
    )
    config = _migration_config()
    command.downgrade(config, "0003_project_create_idempotency")
    assert not asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='context_sources')"
        )
    )
    command.upgrade(config, "head")
    assert asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='context_source_versions')"
        )
    )
