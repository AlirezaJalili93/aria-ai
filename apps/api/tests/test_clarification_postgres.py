from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
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
from app.modules.gaps.application.clarification_service import (
    ClarificationService,
    CreateClarificationQuestionCommand,
    ResolveClarificationCommand,
)
from app.modules.gaps.infrastructure.clarification_repository import (
    SqlAlchemyClarificationUnitOfWorkFactory,
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
    asyncio.run(
        _execute(
            "TRUNCATE clarification_resolutions, clarifications, gap_requirement_links, gaps, "
            "requirements, context_items, usage_records, outbox_events, jobs, "
            "idempotency_records, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed() -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id, gap_id = uuid4(), uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account, :owner, 'Project', 'landing')",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO gaps (id, account_id, project_id, context_version, gap_type, severity) "
        "VALUES (:id, :account, :project, 1, 'missing_information', 'critical')",
        {"id": gap_id, "account": account_id, "project": project_id},
    )
    return user_id, account_id, project_id, gap_id


def test_schema_has_exact_tenant_restrict_rls_and_one_resolution_constraints() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                values = await connection.run_sync(
                    lambda sync: {
                        table: (
                            {column["name"] for column in inspect(sync).get_columns(table)},
                            {
                                fk["name"]: fk.get("options", {}).get("ondelete")
                                for fk in inspect(sync).get_foreign_keys(table)
                            },
                            {item["name"] for item in inspect(sync).get_unique_constraints(table)},
                            {item["name"] for item in inspect(sync).get_indexes(table)},
                        )
                        for table in ("clarifications", "clarification_resolutions")
                    }
                )
                rls = {
                    table: bool(
                        (
                            await connection.execute(
                                text(
                                    "SELECT relrowsecurity FROM pg_catalog.pg_class "
                                    "WHERE oid=to_regclass(:table)"
                                ),
                                {"table": f"public.{table}"},
                            )
                        ).scalar_one()
                    )
                    for table in ("clarifications", "clarification_resolutions")
                }
                grants = int(
                    (
                        await connection.execute(
                            text(
                                "SELECT count(*) FROM information_schema.role_table_grants "
                                "WHERE table_schema='public' "
                                "AND table_name IN ('clarifications','clarification_resolutions') "
                                "AND grantee IN ('anon','authenticated')"
                            )
                        )
                    ).scalar_one()
                )
                return values, rls, grants
        finally:
            await runtime.close()

    values, rls, grants = asyncio.run(inspect_schema())
    question_columns, question_fks, question_uniques, question_indexes = values[
        "clarifications"
    ]
    resolution_columns, resolution_fks, resolution_uniques, resolution_indexes = values[
        "clarification_resolutions"
    ]
    assert question_columns == {
        "id",
        "account_id",
        "project_id",
        "gap_id",
        "question_text",
        "status",
        "created_by_type",
        "created_by",
        "created_at",
        "updated_at",
    }
    assert resolution_columns == {
        "id",
        "account_id",
        "project_id",
        "gap_id",
        "clarification_id",
        "resolution_type",
        "answer_text",
        "author_type",
        "author_id",
        "actor_id",
        "created_at",
    }
    assert set(question_fks.values()) == {"RESTRICT"}
    assert set(resolution_fks.values()) == {"RESTRICT"}
    assert "uq_clarifications_tenant_gap" in question_uniques
    assert "uq_clarification_resolutions_clarification" in resolution_uniques
    assert "ux_clarifications_open_question" in question_indexes
    assert "ix_clarification_resolutions_account_project_gap" in resolution_indexes
    assert rls == {"clarifications": True, "clarification_resolutions": True}
    assert grants == 0


def test_database_rejects_cross_tenant_duplicate_and_invalid_resolution_shape() -> None:
    user_id, account_id, project_id, gap_id = asyncio.run(_seed())
    clarification_id = uuid4()
    insert_question = (
        "INSERT INTO clarifications "
        "(id, account_id, project_id, gap_id, question_text, created_by_type, created_by) "
        "VALUES (:id, :account, :project, :gap, :question, 'user', :creator)"
    )
    values = {
        "id": clarification_id,
        "account": account_id,
        "project": project_id,
        "gap": gap_id,
        "question": "پرسش",
        "creator": user_id,
    }
    asyncio.run(_execute(insert_question, values))
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(insert_question, {**values, "id": uuid4()}))

    _, other_account, _, _ = asyncio.run(_seed())
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(insert_question, {**values, "id": uuid4(), "account": other_account})
        )

    resolution_sql = (
        "INSERT INTO clarification_resolutions "
        "(id, account_id, project_id, gap_id, clarification_id, resolution_type, "
        "answer_text, author_type, actor_id) VALUES "
        "(:id, :account, :project, :gap, :clarification, :type, :answer, :author, :actor)"
    )
    base = {
        "id": uuid4(),
        "account": account_id,
        "project": project_id,
        "gap": gap_id,
        "clarification": clarification_id,
        "type": "accepted_assumption",
        "answer": "synthetic",
        "author": "user",
        "actor": user_id,
    }
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(resolution_sql, base))
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                resolution_sql,
                {**base, "id": uuid4(), "type": "ignored", "answer": None, "author": "system"},
            )
        )


def test_postgres_service_resolves_only_after_last_open_question() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, gap_id = asyncio.run(_seed())
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    logger = create_event_logger(
        service="test",
        environment="test",
        app_version="test",
        release_commit_sha=None,
        level="INFO",
        stream=StringIO(),
    )
    service = ClarificationService(
        SqlAlchemyClarificationUnitOfWorkFactory(runtime.session_factory), logger
    )
    context = TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )

    async def run_flow() -> None:
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
        ):
            first = await service.create_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                command=CreateClarificationQuestionCommand("پرسش اول؟", "question-1"),
            )
            second = await service.create_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                command=CreateClarificationQuestionCommand("پرسش دوم؟", "question-2"),
            )
            await service.resolve_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                clarification_id=first.id,
                command=ResolveClarificationCommand(
                    "provided_information", "پاسخ", "client", "resolution-1"
                ),
            )
            assert await _scalar("SELECT status FROM gaps WHERE id=:id", {"id": gap_id}) == "open"
            await service.resolve_question(
                context,
                project_id=project_id,
                gap_id=gap_id,
                clarification_id=second.id,
                command=ResolveClarificationCommand(
                    "accepted_assumption", None, "user", "resolution-2"
                ),
            )

    try:
        asyncio.run(run_flow())
    finally:
        asyncio.run(runtime.close())
    final_status = asyncio.run(
        _scalar("SELECT status FROM gaps WHERE id=:id", {"id": gap_id})
    )
    assert final_status == "resolved"
    assert int(
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM clarification_resolutions WHERE actor_id=:actor",
                {"actor": user_id},
            )
        )
    ) == 2


def test_migration_downgrades_and_reupgrades() -> None:
    command.downgrade(_migration_config(), "0015_gap_detection")
    assert asyncio.run(_scalar("SELECT to_regclass('public.clarifications') IS NULL")) is True
    command.upgrade(_migration_config(), "head")
    assert asyncio.run(_scalar("SELECT to_regclass('public.clarifications') IS NOT NULL")) is True
