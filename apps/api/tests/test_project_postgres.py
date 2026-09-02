from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import TraceContext, bind_trace_context, create_event_logger
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.identity.infrastructure.account_discovery import SqlAlchemyAccountDiscovery
from app.modules.projects.application.project_service import (
    CreateProjectCommand,
    ProjectApplicationService,
    ProjectIdempotencyConflict,
)
from app.modules.projects.infrastructure.repository import (
    SqlAlchemyProjectRepository,
    SqlAlchemyProjectUnitOfWorkFactory,
)

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
def clean_project_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_identity(*, role: str = "owner", status: str = "active") -> TenantContext:
    subject = uuid4()
    account_id = uuid4()
    membership_id = uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:subject)", {"subject": subject})
    await _execute("INSERT INTO accounts (id) VALUES (:account_id)", {"account_id": account_id})
    await _execute(
        """
        INSERT INTO account_memberships (id, account_id, user_id, role, status)
        VALUES (:membership_id, :account_id, :subject, :role, :status)
        """,
        {
            "membership_id": membership_id,
            "account_id": account_id,
            "subject": subject,
            "role": role,
            "status": status,
        },
    )
    return TenantContext(
        subject_id=subject,
        account_id=account_id,
        membership_id=membership_id,
        role=role,  # type: ignore[arg-type]
        membership_status=status,  # type: ignore[arg-type]
    )


def test_m002_schema_has_approved_constraints_indexes_and_rls() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema() -> tuple[set[str], set[str], set[str], bool]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                columns, indexes, foreign_keys = await connection.run_sync(
                    lambda sync_connection: (
                        {item["name"] for item in inspect(sync_connection).get_columns("projects")},
                        {item["name"] for item in inspect(sync_connection).get_indexes("projects")},
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_foreign_keys("projects")
                        },
                    )
                )
                rls = bool(
                    (
                        await connection.execute(
                            text(
                                """
                                SELECT relrowsecurity
                                FROM pg_catalog.pg_class
                                WHERE oid = 'public.projects'::regclass
                                """
                            )
                        )
                    ).scalar_one()
                )
                return columns, indexes, foreign_keys, rls
        finally:
            await runtime.close()

    columns, indexes, foreign_keys, rls = asyncio.run(inspect_schema())
    assert {
        "id",
        "account_id",
        "owner_id",
        "title",
        "project_type",
        "status",
        "current_context_version",
        "created_at",
        "updated_at",
        "deleted_at",
    } == columns
    assert {
        "ix_projects_account_id_created_at",
        "ix_projects_account_id_status",
        "ix_projects_account_id_project_type",
        "uq_projects_id_account_id",
    } == indexes
    assert {
        "fk_projects_account_id_accounts",
        "fk_projects_owner_id_profiles",
    } == foreign_keys
    assert rls


def test_create_persists_owner_default_status_and_context_zero_with_safe_event() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> tuple[UUID, UUID, StringIO]:
        context = await _seed_identity()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        stream = StringIO()
        logger = create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=stream,
        )
        service = ProjectApplicationService(
            SqlAlchemyProjectUnitOfWorkFactory(runtime.session_factory),
            logger,
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                project = await service.create(
                    context,
                    CreateProjectCommand(
                        title="محتوای خصوصی",
                        project_type="landing",
                        idempotency_key="postgres-create",
                    ),
                )
        finally:
            await runtime.close()
        assert project.owner_id == context.subject_id
        assert project.account_id == context.account_id
        assert project.status == "draft"
        assert project.current_context_version == 0
        return project.id, context.account_id, stream

    project_id, account_id, stream = asyncio.run(scenario())
    assert asyncio.run(
        _scalar(
            "SELECT current_context_version FROM projects WHERE id = :project_id",
            {"project_id": project_id},
        )
    ) == 0
    event = next(
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if json.loads(line)["event_name"] == "project.created"
    )
    assert event["account_id"] == str(account_id)
    assert event["project_id"] == str(project_id)
    assert "محتوای خصوصی" not in stream.getvalue()


def test_database_rejects_invalid_vocabulary_negative_version_and_invalid_owner() -> None:
    context = asyncio.run(_seed_identity())
    base = {
        "id": uuid4(),
        "account_id": context.account_id,
        "owner_id": context.subject_id,
        "title": "Project",
        "project_type": "landing",
        "status": "draft",
        "version": 0,
    }
    statement = """
        INSERT INTO projects (
            id, account_id, owner_id, title, project_type, status, current_context_version
        ) VALUES (
            :id, :account_id, :owner_id, :title, :project_type, :status, :version
        )
    """
    for overrides in (
        {"project_type": "store"},
        {"status": "deleted"},
        {"version": -1},
        {"owner_id": uuid4()},
    ):
        values = {**base, **overrides, "id": uuid4()}
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(statement, values))


def test_repository_is_tenant_scoped_and_soft_delete_is_excluded_by_default() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        context = await _seed_identity(role="admin")
        other = await _seed_identity()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        logger = create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        )
        service = ProjectApplicationService(
            SqlAlchemyProjectUnitOfWorkFactory(runtime.session_factory),
            logger,
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                project = await service.create(
                    context,
                    CreateProjectCommand(
                        title="Project",
                        project_type="corporate",
                        idempotency_key="postgres-soft-delete",
                    ),
                )
                deleted = await service.soft_delete(context, project.id)
            async with runtime.session_factory() as session:
                repository = SqlAlchemyProjectRepository(session)
                assert (
                    await repository.get(account_id=context.account_id, project_id=project.id)
                    is None
                )
                assert await repository.list_by_account(
                    account_id=context.account_id,
                    limit=10,
                    cursor_created_at=None,
                    cursor_id=None,
                ) == ()
                assert (
                    await repository.get(account_id=other.account_id, project_id=project.id)
                    is None
                )
                recovered = await repository.get_including_deleted(
                    account_id=context.account_id,
                    project_id=project.id,
                )
                cross_tenant_recovery = await repository.get_including_deleted(
                    account_id=other.account_id,
                    project_id=project.id,
                )
        finally:
            await runtime.close()
        assert recovered == deleted
        assert cross_tenant_recovery is None

    asyncio.run(scenario())


def test_database_trigger_advances_updated_at_for_all_mutable_tables() -> None:
    context = asyncio.run(_seed_identity())
    project_id = uuid4()
    asyncio.run(
        _execute(
            """
            INSERT INTO projects (id, account_id, owner_id, title, project_type)
            VALUES (:id, :account_id, :owner_id, 'Project', 'portfolio')
            """,
            {
                "id": project_id,
                "account_id": context.account_id,
                "owner_id": context.subject_id,
            },
        )
    )
    before = {
        table: asyncio.run(
            _scalar(
                f"SELECT updated_at FROM {table} WHERE {key} = :id",
                {"id": value},
            )
        )
        for table, key, value in (
            ("accounts", "id", context.account_id),
            ("profiles", "user_id", context.subject_id),
            ("projects", "id", project_id),
        )
    }
    asyncio.run(_execute("SELECT pg_sleep(0.01)"))
    asyncio.run(
        _execute(
            "UPDATE accounts SET status = status WHERE id = :id",
            {"id": context.account_id},
        )
    )
    asyncio.run(
        _execute(
            "UPDATE profiles SET locale = locale WHERE user_id = :id",
            {"id": context.subject_id},
        )
    )
    asyncio.run(
        _execute(
            "UPDATE projects SET title = title WHERE id = :id",
            {"id": project_id},
        )
    )
    for table, key, value in (
        ("accounts", "id", context.account_id),
        ("profiles", "user_id", context.subject_id),
        ("projects", "id", project_id),
    ):
        after = asyncio.run(
            _scalar(
                f"SELECT updated_at FROM {table} WHERE {key} = :id",
                {"id": value},
            )
        )
        assert after > before[table]


def test_m002_downgrade_and_reupgrade_preserve_fail_closed_privileges() -> None:
    config = _migration_config()
    command.downgrade(config, "0001_identity_access_hardening")
    assert not asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables "
            "WHERE schemaname='public' AND tablename='projects')"
        )
    )
    command.upgrade(config, "head")
    assert asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables "
            "WHERE schemaname='public' AND tablename='projects')"
        )
    )
    assert asyncio.run(
        _scalar(
            """
            SELECT count(*)
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND table_name = 'projects'
              AND grantee IN ('anon', 'authenticated')
            """
        )
    ) == 0


def test_account_discovery_returns_only_active_memberships() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> tuple[tuple[UUID, str], ...]:
        context = await _seed_identity(role="owner")
        invited_account = uuid4()
        suspended_account = uuid4()
        await _execute(
            "INSERT INTO accounts (id) VALUES (:invited), (:suspended)",
            {"invited": invited_account, "suspended": suspended_account},
        )
        for account_id, status in (
            (invited_account, "invited"),
            (suspended_account, "suspended"),
        ):
            await _execute(
                """
                INSERT INTO account_memberships (id, account_id, user_id, role, status)
                VALUES (:id, :account_id, :user_id, 'member', :status)
                """,
                {
                    "id": uuid4(),
                    "account_id": account_id,
                    "user_id": context.subject_id,
                    "status": status,
                },
            )
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            discovered = await SqlAlchemyAccountDiscovery(runtime.session_factory).execute(
                AuthenticatedIdentity(subject=context.subject_id)
            )
        finally:
            await runtime.close()
        return tuple((item.id, item.role) for item in discovered)

    values = asyncio.run(scenario())
    assert len(values) == 1
    assert values[0][1] == "owner"


def test_project_create_idempotency_is_persistent_and_concurrency_safe() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> tuple[UUID, UUID, int]:
        context = await _seed_identity()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        logger = create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        )
        service = ProjectApplicationService(
            SqlAlchemyProjectUnitOfWorkFactory(runtime.session_factory), logger
        )

        async def create_once() -> UUID:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                project = await service.create(
                    context,
                    CreateProjectCommand(
                        title="Concurrent",
                        project_type="landing",
                        idempotency_key="concurrent-create",
                    ),
                )
                return project.id

        try:
            first, second = await asyncio.gather(create_once(), create_once())
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ), pytest.raises(ProjectIdempotencyConflict):
                await service.create(
                    context,
                    CreateProjectCommand(
                        title="Different",
                        project_type="landing",
                        idempotency_key="concurrent-create",
                    ),
                )
            count = int(
                await _scalar(
                    "SELECT count(*) FROM projects WHERE account_id = :account_id",
                    {"account_id": context.account_id},
                )
            )
            return first, second, count
        finally:
            await runtime.close()

    first, second, count = asyncio.run(scenario())
    assert first == second
    assert count == 1


def test_project_repository_uses_descending_keyset_without_gaps() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
        context = await _seed_identity()
        project_ids = sorted((uuid4(), uuid4(), uuid4()), reverse=True)
        created_at = datetime.now(UTC)
        for project_id in project_ids:
            await _execute(
                """
                INSERT INTO projects (
                    id, account_id, owner_id, title, project_type, created_at, updated_at
                ) VALUES (
                    :id, :account_id, :owner_id, 'Project', 'portfolio', :created_at, :created_at
                )
                """,
                {
                    "id": project_id,
                    "account_id": context.account_id,
                    "owner_id": context.subject_id,
                    "created_at": created_at,
                },
            )
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.session_factory() as session:
                repository = SqlAlchemyProjectRepository(session)
                first = await repository.list_by_account(
                    account_id=context.account_id,
                    limit=2,
                    cursor_created_at=None,
                    cursor_id=None,
                )
                second = await repository.list_by_account(
                    account_id=context.account_id,
                    limit=2,
                    cursor_created_at=first[-1].created_at,
                    cursor_id=first[-1].id,
                )
        finally:
            await runtime.close()
        return tuple(item.id for item in first), tuple(item.id for item in second)

    first, second = asyncio.run(scenario())
    assert len(first) == 2
    assert len(second) == 1
    assert first + second == tuple(sorted(first + second, reverse=True))
