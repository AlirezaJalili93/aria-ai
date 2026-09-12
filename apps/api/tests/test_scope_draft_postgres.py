from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import TraceContext, bind_trace_context
from sqlalchemy import text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_draft_service import (
    ScopeDraftAccessNotFound,
    ScopeDraftService,
    ScopeDraftStale,
    UpdateScopeSectionCommand,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS, ScopeDraftValidationError
from app.modules.scope.infrastructure.repository import SqlAlchemyScopeDraftUnitOfWorkFactory

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


async def _execute(sql: str, parameters: dict[str, object] | None = None) -> None:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_scope_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE scope_drafts, clarifications, gaps, requirements, context_items, "
            "usage_records, outbox_events, jobs, idempotency_records, "
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


def test_scope_repository_is_tenant_current_cas_atomic_and_stale_safe() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, other_account_id, project_id = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeDraftService(
            SqlAlchemyScopeDraftUnitOfWorkFactory(runtime.session_factory),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                draft = await service.get_current(
                    _context(user_id, account_id), project_id=project_id
                )
                with pytest.raises(ScopeDraftAccessNotFound):
                    await service.get_current(
                        _context(user_id, other_account_id), project_id=project_id
                    )
                updated = await service.update_section(
                    _context(user_id, account_id),
                    project_id=project_id,
                    section_id="summary",
                    command=UpdateScopeSectionCommand("خلاصه", draft.updated_at),
                )
                assert updated.updated_at > draft.updated_at
                assert updated.content["sections"][0]["value"] == "خلاصه"
                with pytest.raises(ScopeDraftValidationError):
                    await service.update_section(
                        _context(user_id, account_id),
                        project_id=project_id,
                        section_id="content",
                        command=UpdateScopeSectionCommand(
                            [{"item_id": "fabricated", "description": "محتوا"}],
                            updated.updated_at,
                        ),
                    )
                await _execute(
                    "UPDATE projects SET current_context_version=2 WHERE id=:id",
                    {"id": project_id},
                )
                with pytest.raises(ScopeDraftStale):
                    await service.update_section(
                        _context(user_id, account_id),
                        project_id=project_id,
                        section_id="summary",
                        command=UpdateScopeSectionCommand("قدیمی", updated.updated_at),
                    )
        finally:
            await runtime.close()

    asyncio.run(scenario())
