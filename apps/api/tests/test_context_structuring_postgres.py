from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_backend_application.context_structuring import (
    ContextStructuringRepositoryError,
    ContextVersionWrite,
)
from sqlalchemy import text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.context.infrastructure.context_structuring_repository import (
    SqlAlchemyContextSnapshotReader,
    SqlAlchemyContextStructuringUnitOfWorkFactory,
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
def clean_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE context_items, usage_records, outbox_events, jobs, idempotency_records, "
            "context_source_versions, context_sources, project_create_requests, projects, "
            "account_memberships, profiles, accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_project() -> tuple[UUID, UUID, UUID]:
    user_id, account_id, project_id = uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account, :owner, 'Project', 'landing')",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    return user_id, account_id, project_id


async def _seed_source(
    *,
    user_id: UUID,
    account_id: UUID,
    project_id: UUID,
    source_status: str = "ready",
) -> tuple[UUID, UUID]:
    source_id, version_id = uuid4(), uuid4()
    await _execute(
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, created_by) "
        "VALUES (:id, :account, :project, 'text', :status, :creator)",
        {
            "id": source_id,
            "account": account_id,
            "project": project_id,
            "status": source_status,
            "creator": user_id,
        },
    )
    await _execute(
        "INSERT INTO context_source_versions "
        "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
        "VALUES (:id, :account, :project, :source, 1, 'version one', 'ready')",
        {
            "id": version_id,
            "account": account_id,
            "project": project_id,
            "source": source_id,
        },
    )
    return source_id, version_id


def test_snapshot_selects_latest_ready_and_excludes_deleted_or_non_ready() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project())
    source_id, _ = asyncio.run(
        _seed_source(user_id=user_id, account_id=account_id, project_id=project_id)
    )
    deleted_source_id, _ = asyncio.run(
        _seed_source(
            user_id=user_id,
            account_id=account_id,
            project_id=project_id,
            source_status="deleted",
        )
    )
    ready_v2, pending_v3 = uuid4(), uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO context_source_versions "
            "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
            "VALUES (:ready, :account, :project, :source, 2, 'version two', 'ready'), "
            "(:pending, :account, :project, :source, 3, NULL, 'pending')",
            {
                "ready": ready_v2,
                "pending": pending_v3,
                "account": account_id,
                "project": project_id,
                "source": source_id,
            },
        )
    )

    async def scenario():
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            return await SqlAlchemyContextSnapshotReader(
                runtime.session_factory
            ).resolve_latest_ready(account_id=account_id, project_id=project_id)
        finally:
            await runtime.close()

    snapshot = asyncio.run(scenario())
    assert len(snapshot) == 1
    assert snapshot[0].source_id == source_id
    assert snapshot[0].source_version_id == ready_v2
    assert snapshot[0].version_no == 2
    assert snapshot[0].canonical_text == "version two"
    assert all(item.source_id != deleted_source_id for item in snapshot)


def test_concurrent_allocations_commit_unique_gap_free_versions() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    assert TEST_DATABASE_URL is not None

    async def persist_one(item_id: UUID) -> int:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with SqlAlchemyContextStructuringUnitOfWorkFactory(
                runtime.session_factory
            )() as unit_of_work:
                version = await unit_of_work.repository.allocate_next_version(
                    account_id=account_id, project_id=project_id
                )
                await unit_of_work.repository.add_batch(
                    (
                        ContextVersionWrite(
                            id=item_id,
                            account_id=account_id,
                            project_id=project_id,
                            context_version=version,
                            item_type="unknown",
                            content=str(item_id),
                            source_refs=(),
                            confidence=None,
                        ),
                    )
                )
                await unit_of_work.repository.advance_project_version(
                    account_id=account_id,
                    project_id=project_id,
                    context_version=version,
                )
                await unit_of_work.commit()
                return version
        finally:
            await runtime.close()

    async def scenario():
        return await asyncio.gather(persist_one(uuid4()), persist_one(uuid4()))

    versions = asyncio.run(scenario())
    assert sorted(versions) == [1, 2]
    assert asyncio.run(
        _scalar(
            "SELECT current_context_version FROM projects WHERE id=:id",
            {"id": project_id},
        )
    ) == 2
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM context_items WHERE project_id=:id",
            {"id": project_id},
        )
    ) == 2


def test_transaction_failure_rolls_back_items_and_version_advance() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            with pytest.raises(ContextStructuringRepositoryError):
                async with SqlAlchemyContextStructuringUnitOfWorkFactory(
                    runtime.session_factory
                )() as unit_of_work:
                    version = await unit_of_work.repository.allocate_next_version(
                        account_id=account_id,
                        project_id=project_id,
                    )
                    await unit_of_work.repository.add_batch(
                        (
                            ContextVersionWrite(
                                id=uuid4(),
                                account_id=account_id,
                                project_id=project_id,
                                context_version=version,
                                item_type="unknown",
                                content="rollback",
                                source_refs=(),
                                confidence=None,
                            ),
                        )
                    )
                    await unit_of_work.repository.advance_project_version(
                        account_id=uuid4(),
                        project_id=project_id,
                        context_version=version,
                    )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert asyncio.run(
        _scalar(
            "SELECT current_context_version FROM projects WHERE id=:id",
            {"id": project_id},
        )
    ) == 0
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM context_items WHERE project_id=:id",
            {"id": project_id},
        )
    ) == 0
