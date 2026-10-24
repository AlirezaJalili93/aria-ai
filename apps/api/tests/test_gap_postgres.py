from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import datetime
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
from app.modules.gaps.application.gap_service import PersistGapUseCase
from app.modules.gaps.domain.gap import GapSourceReference, NewGap
from app.modules.gaps.infrastructure.repository import SqlAlchemyGapUnitOfWorkFactory

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
def clean_gap_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE gaps, requirements, context_items, usage_records, outbox_events, jobs, "
            "idempotency_records, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
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


async def _seed_ready_source(
    *, user_id: UUID, account_id: UUID, project_id: UUID
) -> tuple[UUID, UUID]:
    source_id, source_version_id = uuid4(), uuid4()
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
        "VALUES (:id, :account, :project, :source, 1, 'متن canonical', 'ready')",
        {
            "id": source_version_id,
            "account": account_id,
            "project": project_id,
            "source": source_id,
        },
    )
    return source_id, source_version_id


GAP_INSERT = """
INSERT INTO gaps (
    id, account_id, project_id, context_version, gap_type, severity, status,
    source_refs, resolved_at
) VALUES (
    :id, :account_id, :project_id, :context_version, :gap_type, :severity, :status,
    CAST(:source_refs AS jsonb), :resolved_at
)
"""


def _values(*, account_id: UUID, project_id: UUID) -> dict[str, object]:
    return {
        "id": uuid4(),
        "account_id": account_id,
        "project_id": project_id,
        "context_version": 1,
        "gap_type": "missing_information",
        "severity": "critical",
        "status": "open",
        "source_refs": "[]",
        "resolved_at": None,
    }


def test_m006_schema_is_exact_tenant_safe_and_private() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                schema = await connection.run_sync(
                    lambda sync_connection: (
                        {
                            column["name"]: column
                            for column in inspect(sync_connection).get_columns("gaps")
                        },
                        {index["name"] for index in inspect(sync_connection).get_indexes("gaps")},
                        {
                            fk["name"]: fk.get("options", {}).get("ondelete")
                            for fk in inspect(sync_connection).get_foreign_keys("gaps")
                        },
                    )
                )
                rls = (
                    await connection.execute(
                        text(
                            "SELECT relrowsecurity FROM pg_catalog.pg_class "
                            "WHERE oid='public.gaps'::regclass"
                        )
                    )
                ).scalar_one()
                grants = (
                    await connection.execute(
                        text(
                            "SELECT count(*) FROM information_schema.role_table_grants "
                            "WHERE table_schema='public' AND table_name='gaps' "
                            "AND grantee IN ('anon','authenticated')"
                        )
                    )
                ).scalar_one()
                return (*schema, rls, grants)
        finally:
            await runtime.close()

    columns, indexes, foreign_keys, rls, grants = asyncio.run(inspect_schema())
    assert set(columns) == {
        "id",
        "account_id",
        "project_id",
        "context_version",
        "gap_type",
        "severity",
        "status",
        "source_refs",
        "explanation",
        "suggested_resolution_type",
        "generation_job_id",
        "created_at",
        "updated_at",
        "resolved_at",
    }
    assert columns["status"]["default"] == "'open'::character varying"
    assert columns["source_refs"]["default"] == "'[]'::jsonb"
    assert "ix_gaps_account_project_status_severity" in indexes
    assert foreign_keys == {
        "fk_gaps_account_id_accounts": "RESTRICT",
        "fk_gaps_generation_job_tenant": "RESTRICT",
        "fk_gaps_project_id_account_id_projects": "RESTRICT",
    }
    assert rls is True
    assert grants == 0


def test_database_defaults_and_resolved_at_lifecycle_invariant() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    gap_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO gaps "
            "(id, account_id, project_id, context_version, gap_type, severity) "
            "VALUES (:id, :account, :project, 1, 'missing_information', 'medium')",
            {"id": gap_id, "account": account_id, "project": project_id},
        )
    )
    row = asyncio.run(
        _scalar(
            "SELECT jsonb_build_object('status', status, 'source_refs', source_refs) "
            "FROM gaps WHERE id=:id",
            {"id": gap_id},
        )
    )
    assert row == {"status": "open", "source_refs": []}

    resolution_time = datetime.fromisoformat("2026-09-07T10:00:00+00:00")
    for status in ("open", "dismissed"):
        values = _values(account_id=account_id, project_id=project_id)
        values.update({"status": status, "resolved_at": resolution_time})
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(GAP_INSERT, values))

    resolved = _values(account_id=account_id, project_id=project_id)
    resolved.update({"status": "resolved", "resolved_at": resolution_time})
    asyncio.run(_execute(GAP_INSERT, resolved))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_version", 0),
        ("gap_type", "missing_info"),
        ("severity", "urgent"),
        ("status", "answered"),
        ("source_refs", "{}"),
    ],
)
def test_database_rejects_noncanonical_values(field: str, value: object) -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    values = _values(account_id=account_id, project_id=project_id)
    values[field] = value
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(GAP_INSERT, values))


def test_database_rejects_cross_tenant_project_and_restricts_project_delete() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    _, _, other_project_id = asyncio.run(_seed_project())
    values = _values(account_id=account_id, project_id=other_project_id)
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(GAP_INSERT, values))

    values = _values(account_id=account_id, project_id=project_id)
    asyncio.run(_execute(GAP_INSERT, values))
    with pytest.raises(IntegrityError):
        asyncio.run(_execute("DELETE FROM projects WHERE id=:id", {"id": project_id}))


def test_updated_at_trigger_advances_on_mutation() -> None:
    _, account_id, project_id = asyncio.run(_seed_project())
    values = _values(account_id=account_id, project_id=project_id)
    asyncio.run(_execute(GAP_INSERT, values))
    before = asyncio.run(_scalar("SELECT updated_at FROM gaps WHERE id=:id", {"id": values["id"]}))
    asyncio.run(
        _execute(
            "UPDATE gaps SET severity='high' WHERE id=:id",
            {"id": values["id"]},
        )
    )
    after = asyncio.run(_scalar("SELECT updated_at FROM gaps WHERE id=:id", {"id": values["id"]}))
    assert isinstance(before, datetime)
    assert isinstance(after, datetime)
    assert after > before


def test_use_case_persists_valid_provenance_and_logs_no_content() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project())
    source_id, source_version_id = asyncio.run(
        _seed_ready_source(
            user_id=user_id,
            account_id=account_id,
            project_id=project_id,
        )
    )
    assert TEST_DATABASE_URL is not None
    stream = StringIO()

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            logger = create_event_logger(
                service="test",
                environment="test",
                app_version="test",
                release_commit_sha=None,
                level="INFO",
                stream=stream,
            )
            service = PersistGapUseCase(
                SqlAlchemyGapUnitOfWorkFactory(runtime.session_factory),
                logger,
            )
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                return await service.execute(
                    NewGap(
                        id=uuid4(),
                        account_id=account_id,
                        project_id=project_id,
                        context_version=1,
                        gap_type="ambiguity",
                        severity="high",
                        source_refs=(GapSourceReference(source_id, source_version_id, 0, 3),),
                    )
                )
        finally:
            await runtime.close()

    persisted = asyncio.run(scenario())
    stored_refs = asyncio.run(
        _scalar(
            "SELECT source_refs FROM gaps WHERE id=:id",
            {"id": persisted.id},
        )
    )
    event = json.loads(stream.getvalue())
    assert stored_refs == [
        {
            "source_id": str(source_id),
            "source_version_id": str(source_version_id),
            "start_offset": 0,
            "end_offset": 3,
        }
    ]
    assert event["event_name"] == "gap.created"
    assert event["gap_id"] == str(persisted.id)
    assert "source_refs" not in event
    assert "canonical_text" not in event


def test_gap_migration_downgrades_and_reupgrades() -> None:
    command.downgrade(_migration_config(), "0013_requirement_crud")
    assert asyncio.run(_scalar("SELECT to_regclass('public.gaps') IS NULL")) is True
    command.upgrade(_migration_config(), "head")
    assert asyncio.run(_scalar("SELECT to_regclass('public.gaps') IS NOT NULL")) is True
