from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import TraceContext, bind_trace_context, create_event_logger
from sqlalchemy import inspect, text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.context.application.text_context_ingestion import (
    CreateTextContextCommand,
    CreateTextContextUseCase,
    TextContextIdempotencyConflict,
    TextContextNotFound,
)
from app.modules.context.infrastructure.text_ingestion import (
    SqlAlchemyTextContextIngestionUnitOfWorkFactory,
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


async def _row(sql: str, parameters: dict[str, object] | None = None):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.connect() as connection:
            return (await connection.execute(text(sql), parameters or {})).one()
    finally:
        await runtime.close()


async def _scalar(sql: str, parameters: dict[str, object] | None = None) -> object:
    return (await _row(sql, parameters))[0]


@pytest.fixture(autouse=True)
def clean_text_context_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE idempotency_records, outbox_events, jobs, context_source_versions, "
            "context_sources, project_create_requests, projects, account_memberships, profiles, "
            "accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_project() -> tuple[TenantContext, UUID]:
    user_id, account_id, project_id = uuid4(), uuid4(), uuid4()
    membership_id = uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:user_id)", {"user_id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:account_id)", {"account_id": account_id})
    await _execute(
        "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
        "VALUES (:id, :account_id, :user_id, 'owner', 'active')",
        {"id": membership_id, "account_id": account_id, "user_id": user_id},
    )
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account_id, :user_id, 'Project', 'landing')",
        {"id": project_id, "account_id": account_id, "user_id": user_id},
    )
    return (
        TenantContext(
            subject_id=user_id,
            account_id=account_id,
            membership_id=membership_id,
            role="owner",
            membership_status="active",
        ),
        project_id,
    )


def _run(
    now: datetime,
    context: TenantContext,
    command_: CreateTextContextCommand,
):
    async def scenario():
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        stream = StringIO()
        service = CreateTextContextUseCase(
            SqlAlchemyTextContextIngestionUnitOfWorkFactory(runtime.session_factory),
            create_event_logger(
                service="aria-api",
                environment="test",
                app_version="0.1.0",
                release_commit_sha=None,
                level="INFO",
                stream=stream,
            ),
            clock=lambda: now,
        )
        try:
            with bind_trace_context(
                TraceContext(
                    request_id=str(uuid4()),
                    correlation_id=str(command_.correlation_id),
                )
            ):
                return await service.execute(context, command_), stream
        finally:
            await runtime.close()

    return asyncio.run(scenario())


def test_text_ingestion_persists_one_atomic_content_safe_pipeline_and_replays() -> None:
    context, project_id = asyncio.run(_seed_project())
    now = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    raw_text = "  متن دقیق\r\nبدون trim  "
    command_ = CreateTextContextCommand(
        project_id=project_id,
        raw_text=raw_text,
        idempotency_key="same-key",
        correlation_id=uuid4(),
    )

    first, stream = _run(now, context, command_)
    replay, _ = _run(now, context, command_)
    assert replay == first
    source = asyncio.run(
        _row(
            "SELECT raw_text, checksum, status FROM context_sources WHERE id=:id",
            {"id": first.source_id},
        )
    )
    job = asyncio.run(
        _row(
            "SELECT job_type, status, payload_ref FROM jobs WHERE id=:id",
            {"id": first.job_id},
        )
    )
    outbox = asyncio.run(
        _row(
            "SELECT event_type, status, payload FROM outbox_events WHERE aggregate_id=:id",
            {"id": first.source_id},
        )
    )
    reservation = asyncio.run(
        _row(
            "SELECT response_status, response_ref, expires_at "
            "FROM idempotency_records WHERE idempotency_key='same-key'"
        )
    )
    assert source[0] == raw_text and source[2] == "uploaded"
    assert len(source[1]) == 64 and source[1] == source[1].lower()
    assert job[0:2] == ("context_source_parse", "queued")
    assert set(job[2]) == {"source_id", "source_version_id"}
    assert outbox[0:2] == ("context_added.v1", "pending")
    assert set(outbox[2]) == {
        "jobId",
        "taskType",
        "payloadVersion",
        "accountId",
        "projectId",
        "correlationId",
    }
    assert reservation[0] == 202
    assert reservation[1]["source_id"] == str(first.source_id)
    assert reservation[2] == now + timedelta(hours=24)
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 1
    assert int(asyncio.run(_scalar("SELECT count(*) FROM jobs"))) == 1
    assert raw_text not in stream.getvalue()

    with pytest.raises(TextContextIdempotencyConflict):
        _run(
            now,
            context,
            CreateTextContextCommand(
                project_id=project_id,
                raw_text="different",
                idempotency_key="same-key",
                correlation_id=uuid4(),
            ),
        )
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 1


def test_idempotency_scope_includes_actor_and_expired_record_can_be_replaced() -> None:
    context, project_id = asyncio.run(_seed_project())
    second_user_id, second_membership_id = uuid4(), uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO profiles (user_id) VALUES (:id)",
            {"id": second_user_id},
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
            "VALUES (:id, :account_id, :user_id, 'member', 'active')",
            {
                "id": second_membership_id,
                "account_id": context.account_id,
                "user_id": second_user_id,
            },
        )
    )
    second_context = TenantContext(
        subject_id=second_user_id,
        account_id=context.account_id,
        membership_id=second_membership_id,
        role="member",
        membership_status="active",
    )
    now = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    command_ = CreateTextContextCommand(
        project_id=project_id,
        raw_text="same",
        idempotency_key="actor-key",
        correlation_id=uuid4(),
    )
    first, _ = _run(now, context, command_)
    second_actor, _ = _run(now, second_context, command_)
    expired_replacement, _ = _run(now + timedelta(hours=25), context, command_)

    assert len({first.source_id, second_actor.source_id, expired_replacement.source_id}) == 3
    assert int(asyncio.run(_scalar("SELECT count(*) FROM idempotency_records"))) == 2
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 3


def test_missing_or_cross_tenant_project_rolls_back_every_row() -> None:
    context, _ = asyncio.run(_seed_project())
    _, other_project_id = asyncio.run(_seed_project())
    with pytest.raises(TextContextNotFound):
        _run(
            datetime.now(UTC),
            context,
            CreateTextContextCommand(
                project_id=other_project_id,
                raw_text="valid",
                idempotency_key="missing-project",
                correlation_id=uuid4(),
            ),
        )
    for table in (
        "idempotency_records",
        "context_sources",
        "context_source_versions",
        "jobs",
        "outbox_events",
    ):
        assert int(asyncio.run(_scalar(f"SELECT count(*) FROM {table}"))) == 0


def test_idempotency_schema_scope_rls_grants_and_recovery_are_exact() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                columns, unique_constraints = await connection.run_sync(
                    lambda sync_connection: (
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_columns(
                                "idempotency_records"
                            )
                        },
                        inspect(sync_connection).get_unique_constraints("idempotency_records"),
                    )
                )
                rls = (
                    await connection.execute(
                        text(
                            "SELECT relrowsecurity FROM pg_catalog.pg_class "
                            "WHERE oid='public.idempotency_records'::regclass"
                        )
                    )
                ).scalar_one()
                return columns, unique_constraints, bool(rls)
        finally:
            await runtime.close()

    columns, unique_constraints, rls = asyncio.run(inspect_schema())
    assert columns == {
        "id",
        "account_id",
        "actor_id",
        "route_key",
        "idempotency_key",
        "request_hash",
        "response_status",
        "response_ref",
        "expires_at",
        "created_at",
    }
    scope = next(item for item in unique_constraints if item["name"] == "uq_idempotency_scope_key")
    assert scope["column_names"] == [
        "account_id",
        "actor_id",
        "route_key",
        "idempotency_key",
    ]
    assert rls
    assert (
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='public' AND table_name='idempotency_records' "
                "AND grantee IN ('anon','authenticated')"
            )
        )
        == 0
    )
    config = _migration_config()
    command.downgrade(config, "0005_jobs_outbox")
    assert not asyncio.run(
        _scalar(
            "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
            "AND tablename='idempotency_records')"
        )
    )
    command.upgrade(config, "head")
