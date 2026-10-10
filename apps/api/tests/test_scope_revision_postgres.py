from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
from app.modules.scope.application.scope_revision_ports import ScopeRevisionRepositoryError
from app.modules.scope.application.scope_revision_service import (
    CreateScopeRevisionCommand,
    ScopeRevisionAccessNotFound,
    ScopeRevisionService,
    ScopeRevisionStale,
)
from app.modules.scope.application.scope_version_service import (
    CreateScopeVersionCommand,
    ScopeRevisionRequired,
    ScopeVersionService,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS
from app.modules.scope.domain.scope_version import hash_scope_snapshot
from app.modules.scope.infrastructure.revision_repository import (
    SqlAlchemyScopeRevisionUnitOfWorkFactory,
)
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
def clean_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE scope_change_requests, scope_approvals, scope_share_links, "
            "scope_versions, scope_drafts, clarifications, gaps, requirements, context_items, "
            "usage_records, outbox_events, jobs, idempotency_records, context_source_versions, "
            "context_sources, project_create_requests, projects, account_memberships, profiles, "
            "accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


def _content(summary: str) -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": summary
                if section_id == "summary"
                else ("" if section_id == "visual_direction" else []),
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
            for section_id in SECTION_IDS
        ],
    }


async def _seed() -> tuple[UUID, UUID, UUID, UUID, UUID, datetime]:
    user_id, account_id, other_account_id, project_id = uuid4(), uuid4(), uuid4(), uuid4()
    target_id, share_link_id, change_request_id = uuid4(), uuid4(), uuid4()
    original, revised = _content("نسخه اولیه"), _content("نسخه اصلاح‌شده")
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute(
        "INSERT INTO accounts (id) VALUES (:account), (:other)",
        {"account": account_id, "other": other_account_id},
    )
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) "
        "VALUES (:id, :account, :owner, 'Project', 'landing', 1)",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO scope_drafts "
        "(account_id, project_id, context_version, content, updated_by_type, updated_by) "
        "VALUES (:account, :project, 1, CAST(:content AS jsonb), 'user', :user)",
        {
            "account": account_id,
            "project": project_id,
            "content": json.dumps(revised),
            "user": user_id,
        },
    )
    await _execute(
        "INSERT INTO scope_versions "
        "(id, account_id, project_id, version_no, context_version, status, snapshot_data, "
        "snapshot_hash, created_by) VALUES "
        "(:id, :account, :project, 1, 1, 'changes_requested', CAST(:content AS jsonb), "
        ":hash, :user)",
        {
            "id": target_id,
            "account": account_id,
            "project": project_id,
            "content": json.dumps(original),
            "hash": hash_scope_snapshot(original),
            "user": user_id,
        },
    )
    await _execute(
        "INSERT INTO scope_share_links "
        "(id, account_id, project_id, scope_version_id, token_hash, expires_at, created_by) "
        "VALUES (:id, :account, :project, :version, :hash, :expires, :user)",
        {
            "id": share_link_id,
            "account": account_id,
            "project": project_id,
            "version": target_id,
            "hash": b"x" * 32,
            "expires": datetime.now(UTC) + timedelta(days=1),
            "user": user_id,
        },
    )
    await _execute(
        "INSERT INTO scope_change_requests "
        "(id, account_id, project_id, scope_version_id, share_link_id, version_no, "
        "version_hash, guest_name, comment, idempotency_key, request_hash) VALUES "
        "(:id, :account, :project, :version, :share, 1, :hash, 'Guest', 'Revise', "
        "'guest-key', :request_hash)",
        {
            "id": change_request_id,
            "account": account_id,
            "project": project_id,
            "version": target_id,
            "share": share_link_id,
            "hash": hash_scope_snapshot(original),
            "request_hash": "a" * 64,
        },
    )
    updated = (
        await _execute(
            "SELECT updated_at FROM scope_drafts WHERE project_id=:project",
            {"project": project_id},
        )
    ).scalar_one()
    return user_id, account_id, other_account_id, project_id, change_request_id, updated


def _context(user_id: UUID, account_id: UUID) -> TenantContext:
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def test_revision_is_atomic_replayable_and_preserves_historical_link() -> None:
    assert TEST_DATABASE_URL is not None
    user, account, other, project, change_request, updated = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeRevisionService(
            SqlAlchemyScopeRevisionUnitOfWorkFactory(runtime.session_factory),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            command_value = CreateScopeRevisionCommand(change_request, updated, "revision-1")
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                created = await service.create(
                    _context(user, account),
                    project_id=project,
                    target_version_no=1,
                    command=command_value,
                )
                replayed = await service.create(
                    _context(user, account),
                    project_id=project,
                    target_version_no=1,
                    command=command_value,
                )
                assert created.replayed is False
                assert replayed.replayed is True
                assert replayed.version.id == created.version.id
                with pytest.raises(ScopeRevisionAccessNotFound):
                    await service.create(
                        _context(user, other),
                        project_id=project,
                        target_version_no=1,
                        command=CreateScopeRevisionCommand(
                            change_request, updated, "cross-tenant"
                        ),
                    )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    rows = (
        asyncio.run(
            _execute(
                "SELECT id, version_no, status, revision_of_scope_version_id, change_request_id "
                "FROM scope_versions WHERE project_id=:project ORDER BY version_no",
                {"project": project},
            )
        )
    ).all()
    assert len(rows) == 2
    assert rows[0].status == "superseded"
    assert rows[1].version_no == 2
    assert rows[1].status == "awaiting_approval"
    assert rows[1].revision_of_scope_version_id == rows[0].id
    assert rows[1].change_request_id == change_request
    link_target = asyncio.run(
        _execute(
            "SELECT scope_version_id FROM scope_share_links WHERE project_id=:project",
            {"project": project},
        )
    ).scalar_one()
    assert link_target == rows[0].id


def test_concurrent_different_keys_consume_change_request_once() -> None:
    assert TEST_DATABASE_URL is not None
    user, account, _, project, change_request, updated = asyncio.run(_seed())

    async def scenario() -> list[object]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeRevisionService(
            SqlAlchemyScopeRevisionUnitOfWorkFactory(runtime.session_factory),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            async def revise(key: str):
                with bind_trace_context(
                    TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
                ):
                    return await service.create(
                        _context(user, account),
                        project_id=project,
                        target_version_no=1,
                        command=CreateScopeRevisionCommand(change_request, updated, key),
                    )

            return list(
                await asyncio.gather(
                    revise("revision-a"), revise("revision-b"), return_exceptions=True
                )
            )
        finally:
            await runtime.close()

    results = asyncio.run(scenario())
    assert sum(not isinstance(value, Exception) for value in results) == 1
    assert sum(isinstance(value, ScopeRevisionStale) for value in results) == 1
    count = asyncio.run(
        _execute(
            "SELECT count(*) FROM scope_versions WHERE change_request_id=:change_request",
            {"change_request": change_request},
        )
    ).scalar_one()
    assert count == 1


def test_k05_bypass_guard_and_failed_insert_leave_target_unchanged() -> None:
    assert TEST_DATABASE_URL is not None
    user, account, _, project, change_request, updated = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            freeze = ScopeVersionService(
                SqlAlchemyScopeVersionUnitOfWorkFactory(runtime.session_factory),
                FakeLogger(),  # type: ignore[arg-type]
            )
            target_id = await _target_id_async(project)
            failing = ScopeRevisionService(
                SqlAlchemyScopeRevisionUnitOfWorkFactory(runtime.session_factory),
                FakeLogger(),  # type: ignore[arg-type]
                id_factory=lambda: target_id,
            )
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                with pytest.raises(ScopeRevisionRequired):
                    await freeze.create(
                        _context(user, account),
                        project_id=project,
                        command=CreateScopeVersionCommand(updated, "bypass"),
                    )
                with pytest.raises(ScopeRevisionRepositoryError):
                    await failing.create(
                        _context(user, account),
                        project_id=project,
                        target_version_no=1,
                        command=CreateScopeRevisionCommand(change_request, updated, "fails"),
                    )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    state = asyncio.run(
        _execute(
            "SELECT count(*) AS count, min(status) AS status FROM scope_versions "
            "WHERE project_id=:project",
            {"project": project},
        )
    ).one()
    assert (state.count, state.status) == (1, "changes_requested")


async def _target_id_async(project_id: UUID) -> UUID:
    return (
        await _execute(
            "SELECT id FROM scope_versions WHERE project_id=:project AND version_no=1",
            {"project": project_id},
        )
    ).scalar_one()


def test_revision_lineage_constraints_and_immutability_are_database_enforced() -> None:
    _, account, _, project, change_request, _ = asyncio.run(_seed())
    target = asyncio.run(_target_id_async(project))
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "INSERT INTO scope_versions "
                "(account_id, project_id, version_no, context_version, status, snapshot_data, "
                "snapshot_hash, created_by, revision_of_scope_version_id) "
                "SELECT account_id, project_id, 2, context_version, 'awaiting_approval', "
                "snapshot_data, snapshot_hash, created_by, id FROM scope_versions WHERE id=:id",
                {"id": target},
            )
        )
    await_result = asyncio.run(
        _execute(
            "SELECT relrowsecurity FROM pg_class WHERE oid='public.scope_versions'::regclass"
        )
    ).scalar_one()
    assert await_result is True
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE scope_versions SET change_request_id=:change_request WHERE id=:id",
                {"change_request": change_request, "id": target},
            )
        )
