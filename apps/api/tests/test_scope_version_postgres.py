from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import TraceContext, bind_trace_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_version_service import (
    CreateScopeVersionCommand,
    ScopeVersionAccessNotFound,
    ScopeVersionIdempotencyConflict,
    ScopeVersionService,
    ScopeVersionUnchanged,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS
from app.modules.scope.infrastructure.version_repository import (
    SqlAlchemyScopeVersionUnitOfWorkFactory,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)
API_ROOT = Path(__file__).parents[1]


class FakeLogger:
    def emit(self, event_name: str, **fields: object) -> None:
        del event_name, fields


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


@pytest.fixture(autouse=True)
def clean_scope_version_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE scope_versions, scope_drafts, clarifications, gaps, requirements, "
            "context_items, usage_records, outbox_events, jobs, idempotency_records, "
            "context_source_versions, context_sources, project_create_requests, projects, "
            "account_memberships, profiles, accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


def _content() -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": [] if section_id not in {"summary", "visual_direction"} else "",
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
            for section_id in SECTION_IDS
        ],
    }


async def _seed() -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, other_account_id, project_id = uuid4(), uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute(
        "INSERT INTO accounts (id) VALUES (:id), (:other)",
        {"id": account_id, "other": other_account_id},
    )
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) "
        "VALUES (:id, :account, :owner, 'Project', 'landing', 1)",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO scope_drafts "
        "(account_id, project_id, context_version, content, updated_by_type) "
        "VALUES (:account, :project, 1, CAST(:content AS jsonb), 'system')",
        {"account": account_id, "project": project_id, "content": json.dumps(_content())},
    )
    return user_id, account_id, other_account_id, project_id


def _context(user_id: UUID, account_id: UUID) -> TenantContext:
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


async def _draft_updated_at(project_id: UUID):
    result = await _execute(
        "SELECT updated_at FROM scope_drafts WHERE project_id=:project", {"project": project_id}
    )
    return result.scalar_one()


def test_scope_version_service_replay_duplicate_and_tenant_isolation() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, other_account_id, project_id = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeVersionService(
            SqlAlchemyScopeVersionUnitOfWorkFactory(runtime.session_factory),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            updated_at = await _draft_updated_at(project_id)
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                created = await service.create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeVersionCommand(updated_at, "freeze-1"),
                )
                replayed = await service.create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeVersionCommand(updated_at, "freeze-1"),
                )
                assert replayed == created
                with pytest.raises(ScopeVersionUnchanged):
                    await service.create(
                        _context(user_id, account_id),
                        project_id=project_id,
                        command=CreateScopeVersionCommand(updated_at, "freeze-2"),
                    )
                with pytest.raises(ScopeVersionIdempotencyConflict):
                    await service.create(
                        _context(user_id, account_id),
                        project_id=project_id,
                        command=CreateScopeVersionCommand(
                            updated_at + timedelta(seconds=1), "freeze-1"
                        ),
                    )
                with pytest.raises(ScopeVersionAccessNotFound):
                    await service.get(
                        _context(user_id, other_account_id),
                        project_id=project_id,
                        version_no=1,
                    )
                listed = await service.list(
                    _context(user_id, account_id),
                    project_id=project_id,
                    limit=20,
                    before_version_no=None,
                )
                assert listed == (created,)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_scope_version_snapshot_is_database_immutable_but_status_is_projected() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, _, project_id = asyncio.run(_seed())

    async def create() -> UUID:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            service = ScopeVersionService(
                SqlAlchemyScopeVersionUnitOfWorkFactory(runtime.session_factory),
                FakeLogger(),  # type: ignore[arg-type]
            )
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                version = await service.create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeVersionCommand(
                        await _draft_updated_at(project_id), "freeze"
                    ),
                )
                return version.id

        finally:
            await runtime.close()

    version_id = asyncio.run(create())
    asyncio.run(
        _execute("UPDATE scope_versions SET status='approved' WHERE id=:id", {"id": version_id})
    )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE scope_versions SET snapshot_hash=:hash WHERE id=:id",
                {"id": version_id, "hash": "sha256:" + "0" * 64},
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(_execute("DELETE FROM scope_versions WHERE id=:id", {"id": version_id}))


def test_concurrent_freeze_has_one_version_number_and_one_duplicate_rejection() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, _, project_id = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeVersionService(
            SqlAlchemyScopeVersionUnitOfWorkFactory(runtime.session_factory),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            updated_at = await _draft_updated_at(project_id)

            async def freeze(key: str):
                with bind_trace_context(
                    TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
                ):
                    return await service.create(
                        _context(user_id, account_id),
                        project_id=project_id,
                        command=CreateScopeVersionCommand(updated_at, key),
                    )

            results = await asyncio.gather(
                freeze("concurrent-a"), freeze("concurrent-b"), return_exceptions=True
            )
            assert sum(not isinstance(result, Exception) for result in results) == 1
            assert sum(isinstance(result, ScopeVersionUnchanged) for result in results) == 1
        finally:
            await runtime.close()

    asyncio.run(scenario())
    result = asyncio.run(
        _execute(
            "SELECT count(*) AS count, min(version_no) AS minimum, "
            "max(version_no) AS maximum FROM scope_versions WHERE project_id=:project",
            {"project": project_id},
        )
    ).one()
    assert (result.count, result.minimum, result.maximum) == (1, 1, 1)


def test_scope_version_schema_rls_grants_and_recovery() -> None:
    result = asyncio.run(
        _execute(
            "SELECT c.relrowsecurity, "
            "(SELECT count(*) FROM information_schema.role_table_grants g "
            " WHERE g.table_schema='public' AND g.table_name='scope_versions' "
            " AND g.grantee IN ('anon','authenticated')) AS data_api_grants "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname='scope_versions'"
        )
    )
    row = result.one()
    assert row.relrowsecurity is True
    assert row.data_api_grants == 0

    command.downgrade(_migration_config(), "0017_scope_drafts")
    missing = asyncio.run(_execute("SELECT to_regclass('public.scope_versions')"))
    assert missing.scalar_one() is None
    command.upgrade(_migration_config(), "head")
