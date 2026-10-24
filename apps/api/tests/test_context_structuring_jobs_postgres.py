from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import TraceContext, bind_trace_context, create_event_logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.context.application.context_structuring_job_ports import (
    ContextStructuringActiveJobConflict,
)
from app.modules.context.application.context_structuring_jobs import (
    ContextStructuringProjectNotFound,
    ExplicitSyntheticContextStructuringProjects,
    ScheduleContextStructuringCommand,
    ScheduleContextStructuringUseCase,
)
from app.modules.context.infrastructure.context_structuring_jobs import (
    SqlAlchemyContextStructuringJobUnitOfWorkFactory,
)
from app.modules.identity.application.tenant_context import TenantContext

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
    asyncio.run(_execute("TRUNCATE public.accounts CASCADE"))
    yield


async def _seed() -> tuple[TenantContext, UUID]:
    user_id, account_id, project_id = uuid4(), uuid4(), uuid4()
    source_id, version_id = uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
        "VALUES (:id, :account, :user, 'owner', 'active')",
        {"id": uuid4(), "account": account_id, "user": user_id},
    )
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account, :owner, 'Synthetic', 'landing')",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, created_by) "
        "VALUES (:id, :account, :project, 'text', 'ready', :creator)",
        {
            "id": source_id,
            "account": account_id,
            "project": project_id,
            "creator": user_id,
        },
    )
    await _execute(
        "INSERT INTO context_source_versions "
        "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
        "VALUES (:id, :account, :project, :source, 1, 'SYNTHETIC', 'ready')",
        {
            "id": version_id,
            "account": account_id,
            "project": project_id,
            "source": source_id,
        },
    )
    return (
        TenantContext(
            subject_id=user_id,
            account_id=account_id,
            membership_id=uuid4(),
            role="owner",
            membership_status="active",
        ),
        project_id,
    )


async def _service(
    context: TenantContext,
    project_id: UUID,
) -> tuple[ScheduleContextStructuringUseCase, DatabaseRuntime]:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    return (
        ScheduleContextStructuringUseCase(
            SqlAlchemyContextStructuringJobUnitOfWorkFactory(runtime.session_factory),
            create_event_logger(
                service="aria-api",
                environment="test",
                app_version="0.1.0",
                release_commit_sha=None,
                level="INFO",
            ),
            ExplicitSyntheticContextStructuringProjects(
                frozenset({(context.account_id, project_id)})
            ),
        ),
        runtime,
    )


def test_exact_replay_returns_one_job_and_one_outbox_row() -> None:
    context, project_id = asyncio.run(_seed())

    async def scenario() -> tuple[UUID, UUID]:
        service, runtime = await _service(context, project_id)
        try:
            command_value = ScheduleContextStructuringCommand(
                project_id=project_id,
                idempotency_key="same-command",
                correlation_id=uuid4(),
            )
            first = await service.execute(context, command_value)
            replay = await service.execute(context, command_value)
            assert first.status_url == f"/api/v1/jobs/{first.job_id}"
            assert replay.status_url == first.status_url
            return first.job_id, replay.job_id
        finally:
            await runtime.close()

    with bind_trace_context(TraceContext(correlation_id=str(uuid4()))):
        first_job_id, replay_job_id = asyncio.run(scenario())
    assert replay_job_id == first_job_id
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM jobs WHERE project_id=:project_id "
            "AND job_type='context_structuring'",
            {"project_id": project_id},
        )
    ) == 1
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM outbox_events WHERE aggregate_id=:project_id "
            "AND event_type='context.structuring_requested.v1'",
            {"project_id": project_id},
        )
    ) == 1


def test_database_prevents_two_concurrent_active_jobs_for_project() -> None:
    context, project_id = asyncio.run(_seed())

    async def schedule(key: str) -> object:
        service, runtime = await _service(context, project_id)
        try:
            return await service.execute(
                context,
                ScheduleContextStructuringCommand(project_id, key, uuid4()),
            )
        finally:
            await runtime.close()

    async def scenario() -> tuple[object, object]:
        values = await asyncio.gather(
            schedule("concurrent-a"),
            schedule("concurrent-b"),
            return_exceptions=True,
        )
        return values[0], values[1]

    with bind_trace_context(TraceContext(correlation_id=str(uuid4()))):
        outcomes = asyncio.run(scenario())
    assert sum(isinstance(value, ContextStructuringActiveJobConflict) for value in outcomes) == 1
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM jobs WHERE project_id=:project_id "
            "AND job_type='context_structuring' AND status IN ('queued','running')",
            {"project_id": project_id},
        )
    ) == 1


def test_cross_tenant_project_stops_before_idempotency_persistence() -> None:
    _, project_id = asyncio.run(_seed())
    foreign_user_id, foreign_account_id, foreign_membership_id = uuid4(), uuid4(), uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO profiles (user_id) VALUES (:user_id)",
            {"user_id": foreign_user_id},
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO accounts (id) VALUES (:account_id)",
            {"account_id": foreign_account_id},
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
            "VALUES (:membership_id, :account_id, :user_id, 'member', 'active')",
            {
                "user_id": foreign_user_id,
                "account_id": foreign_account_id,
                "membership_id": foreign_membership_id,
            },
        )
    )
    foreign_context = TenantContext(
        subject_id=foreign_user_id,
        account_id=foreign_account_id,
        membership_id=foreign_membership_id,
        role="member",
        membership_status="active",
    )

    async def scenario() -> None:
        service, runtime = await _service(foreign_context, project_id)
        try:
            with pytest.raises(ContextStructuringProjectNotFound):
                await service.execute(
                    foreign_context,
                    ScheduleContextStructuringCommand(project_id, "foreign", uuid4()),
                )
        finally:
            await runtime.close()

    with bind_trace_context(TraceContext(correlation_id=str(uuid4()))):
        asyncio.run(scenario())
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM idempotency_records WHERE account_id=:account_id",
            {"account_id": foreign_account_id},
        )
    ) == 0


def test_worker_role_has_only_required_project_and_context_item_authority() -> None:
    context, project_id = asyncio.run(_seed())

    async def allowed_operations() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(text("SET LOCAL ROLE aria_worker"))
                assert (
                    await connection.scalar(
                        text(
                            "SELECT current_context_version FROM public.projects "
                            "WHERE id=:project_id"
                        ),
                        {"project_id": project_id},
                    )
                    == 0
                )
                await connection.execute(
                    text(
                        "UPDATE public.projects SET current_context_version=1 "
                        "WHERE id=:project_id"
                    ),
                    {"project_id": project_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.context_items "
                        "(id, account_id, project_id, context_version, item_type, content, "
                        "source_refs, confidence, status, created_by_type, created_by) "
                        "VALUES (:id, :account_id, :project_id, 1, 'reference', "
                        "'SYNTHETIC', CAST('[]' AS jsonb), 1, 'proposed', 'ai', NULL)"
                    ),
                    {
                        "id": uuid4(),
                        "account_id": context.account_id,
                        "project_id": project_id,
                    },
                )
        finally:
            await runtime.close()

    async def forbidden_project_title_update() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            with pytest.raises(SQLAlchemyError):
                async with runtime.engine.begin() as connection:
                    await connection.execute(text("SET LOCAL ROLE aria_worker"))
                    await connection.execute(
                        text("UPDATE public.projects SET title='forbidden' WHERE id=:id"),
                        {"id": project_id},
                    )
        finally:
            await runtime.close()

    asyncio.run(allowed_operations())
    asyncio.run(forbidden_project_title_update())
    assert asyncio.run(
        _scalar("SELECT title FROM projects WHERE id=:id", {"id": project_id})
    ) == "Synthetic"
