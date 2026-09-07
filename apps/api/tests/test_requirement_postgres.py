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
from app.modules.requirements.application.requirement_service import (
    PersistRequirementUseCase,
    RequirementContextVersionError,
    RequirementProvenanceError,
)
from app.modules.requirements.domain.requirement import (
    NewRequirement,
    RequirementSourceReference,
)
from app.modules.requirements.infrastructure.repository import (
    SqlAlchemyRequirementUnitOfWorkFactory,
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
def clean_requirement_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE requirements, context_items, usage_records, outbox_events, jobs, "
            "idempotency_records, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_project(*, current_context_version: int = 2) -> tuple[UUID, UUID, UUID]:
    user_id, account_id, project_id = uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) "
        "VALUES (:id, :account, :owner, 'Project', 'landing', :version)",
        {
            "id": project_id,
            "account": account_id,
            "owner": user_id,
            "version": current_context_version,
        },
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


REQUIREMENT_INSERT = """
INSERT INTO requirements (
    id, account_id, project_id, context_version, category, title, description,
    priority, status, source_refs, confidence, created_by_type, created_by
) VALUES (
    :id, :account_id, :project_id, :context_version, :category, :title, :description,
    :priority, :status, CAST(:source_refs AS jsonb), :confidence, :created_by_type, :created_by
)
"""


def _values(*, user_id: UUID, account_id: UUID, project_id: UUID) -> dict[str, object]:
    return {
        "id": uuid4(),
        "account_id": account_id,
        "project_id": project_id,
        "context_version": 1,
        "category": "functional",
        "title": "عنوان نیازمندی",
        "description": "شرح نیازمندی",
        "priority": "must",
        "status": "draft",
        "source_refs": "[]",
        "confidence": "0.7500",
        "created_by_type": "user",
        "created_by": user_id,
    }


def test_m005_schema_fields_indexes_rls_and_restrictive_foreign_keys() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                schema = await connection.run_sync(
                    lambda sync_connection: (
                        {
                            column["name"]: column
                            for column in inspect(sync_connection).get_columns("requirements")
                        },
                        {
                            index["name"]
                            for index in inspect(sync_connection).get_indexes("requirements")
                        },
                        {
                            fk["name"]: fk.get("options", {}).get("ondelete")
                            for fk in inspect(sync_connection).get_foreign_keys("requirements")
                        },
                    )
                )
                rls = (
                    await connection.execute(
                        text(
                            "SELECT relrowsecurity FROM pg_catalog.pg_class "
                            "WHERE oid='public.requirements'::regclass"
                        )
                    )
                ).scalar_one()
                return (*schema, rls)
        finally:
            await runtime.close()

    columns, indexes, foreign_keys, rls = asyncio.run(inspect_schema())
    assert set(columns) == {
        "id",
        "account_id",
        "project_id",
        "context_version",
        "category",
        "title",
        "description",
        "priority",
        "status",
        "source_refs",
        "confidence",
        "is_unsupported",
        "duplicate_group_key",
        "generation_job_id",
        "created_by_type",
        "created_by",
        "created_at",
        "updated_at",
    }
    assert columns["title"]["nullable"] is False
    assert columns["priority"]["nullable"] is False
    assert columns["priority"]["default"] is None
    assert columns["confidence"]["type"].precision == 5
    assert columns["confidence"]["type"].scale == 4
    assert {
        "ix_requirements_account_project_status_category",
        "ix_requirements_account_project_generation_job",
        "ix_requirements_created_by",
    }.issubset(indexes)
    assert foreign_keys == {
        "fk_requirements_account_id_accounts": "RESTRICT",
        "fk_requirements_project_id_account_id_projects": "RESTRICT",
        "fk_requirements_created_by_profiles": "RESTRICT",
        "fk_requirements_generation_job_id_jobs": "RESTRICT",
    }
    assert rls is True


def test_database_defaults_status_and_empty_provenance_without_priority_default() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project())
    requirement_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO requirements "
            "(id, account_id, project_id, context_version, category, title, description, "
            "priority, created_by_type, created_by) "
            "VALUES (:id, :account, :project, 1, 'content', 'Title', 'Description', "
            "'could', 'user', :creator)",
            {
                "id": requirement_id,
                "account": account_id,
                "project": project_id,
                "creator": user_id,
            },
        )
    )
    row = asyncio.run(
        _scalar(
            "SELECT json_build_object('status', status, 'source_refs', source_refs, "
            "'is_unsupported', is_unsupported) "
            "FROM requirements WHERE id=:id",
            {"id": requirement_id},
        )
    )
    assert row == {"status": "draft", "source_refs": [], "is_unsupported": False}

    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                "INSERT INTO requirements "
                "(account_id, project_id, context_version, category, title, description, "
                "created_by_type) VALUES "
                "(:account, :project, 1, 'content', 'Title', 'Description', 'ai')",
                {"account": account_id, "project": project_id},
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_version", 0),
        ("category", "security"),
        ("priority", "medium"),
        ("status", "active"),
        ("created_by_type", "system"),
        ("confidence", "-0.0001"),
        ("confidence", "1.0001"),
        ("source_refs", "{}"),
    ],
)
def test_database_rejects_invalid_contract_values(field: str, value: object) -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project())
    values = _values(user_id=user_id, account_id=account_id, project_id=project_id)
    values[field] = value
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(REQUIREMENT_INSERT, values))


def test_database_rejects_missing_title_description_and_user_creator() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project())
    values = _values(user_id=user_id, account_id=account_id, project_id=project_id)
    for overrides in (
        {"title": None},
        {"description": None},
        {"created_by": None},
    ):
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(REQUIREMENT_INSERT, {**values, **overrides, "id": uuid4()}))


def test_database_rejects_cross_tenant_project_and_data_api_grants() -> None:
    user_id, account_id, _ = asyncio.run(_seed_project())
    _, _, other_project_id = asyncio.run(_seed_project())
    values = _values(user_id=user_id, account_id=account_id, project_id=other_project_id)
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(REQUIREMENT_INSERT, values))

    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE table_schema='public' AND table_name='requirements' "
            "AND grantee IN ('anon','authenticated')"
        )
    ) == 0


def test_application_persists_valid_provenance_and_rejects_future_context() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project(current_context_version=2))
    source_id, source_version_id = asyncio.run(
        _seed_ready_source(user_id=user_id, account_id=account_id, project_id=project_id)
    )
    assert TEST_DATABASE_URL is not None
    stream = StringIO()
    requirement = NewRequirement(
        id=uuid4(),
        account_id=account_id,
        project_id=project_id,
        context_version=2,
        category="technical",
        title="عنوان محرمانه",
        description="شرح محرمانه",
        priority="should",
        source_refs=(
            RequirementSourceReference(source_id, source_version_id, 0, 3),
        ),
        confidence=None,
        created_by_type="ai",
        created_by=None,
    )

    async def scenario() -> tuple[object, object]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        logger = create_event_logger(
            service="test",
            environment="test",
            app_version="test",
            release_commit_sha=None,
            level="INFO",
            stream=stream,
        )
        service = PersistRequirementUseCase(
            SqlAlchemyRequirementUnitOfWorkFactory(runtime.session_factory), logger
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                persisted = await service.execute(requirement)
                with pytest.raises(RequirementContextVersionError):
                    await service.execute(
                        NewRequirement(
                            id=uuid4(),
                            account_id=account_id,
                            project_id=project_id,
                            context_version=3,
                            category="technical",
                            title="Future",
                            description="Future",
                            priority="must",
                            source_refs=(),
                            confidence=None,
                            created_by_type="ai",
                            created_by=None,
                        )
                    )
            async with runtime.engine.connect() as connection:
                source_refs = (
                    await connection.execute(
                        text("SELECT source_refs FROM requirements WHERE id=:id"),
                        {"id": requirement.id},
                    )
                ).scalar_one()
            return persisted, source_refs
        finally:
            await runtime.close()

    persisted, source_refs = asyncio.run(scenario())
    assert persisted.id == requirement.id
    assert source_refs == [
        {
            "source_id": str(source_id),
            "source_version_id": str(source_version_id),
            "start_offset": 0,
            "end_offset": 3,
        }
    ]
    assert requirement.title not in stream.getvalue()
    assert requirement.description not in stream.getvalue()


def test_application_rejects_cross_tenant_or_non_ready_provenance() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project(current_context_version=1))
    _, other_account_id, other_project_id = asyncio.run(
        _seed_project(current_context_version=1)
    )
    source_id, source_version_id = asyncio.run(
        _seed_ready_source(
            user_id=user_id,
            account_id=account_id,
            project_id=project_id,
        )
    )
    assert TEST_DATABASE_URL is not None
    invalid = NewRequirement(
        id=uuid4(),
        account_id=other_account_id,
        project_id=other_project_id,
        context_version=1,
        category="visual",
        title="Title",
        description="Description",
        priority="could",
        source_refs=(RequirementSourceReference(source_id, source_version_id),),
        confidence=None,
        created_by_type="ai",
        created_by=None,
    )

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        logger = create_event_logger(
            service="test",
            environment="test",
            app_version="test",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        )
        try:
            service = PersistRequirementUseCase(
                SqlAlchemyRequirementUnitOfWorkFactory(runtime.session_factory), logger
            )
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ), pytest.raises(RequirementProvenanceError):
                await service.execute(invalid)
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert asyncio.run(_scalar("SELECT count(*) FROM requirements")) == 0


def test_requirement_updated_at_trigger_and_migration_recovery() -> None:
    user_id, account_id, project_id = asyncio.run(_seed_project())
    values = _values(user_id=user_id, account_id=account_id, project_id=project_id)
    asyncio.run(_execute(REQUIREMENT_INSERT, values))
    before = asyncio.run(
        _scalar("SELECT updated_at FROM requirements WHERE id=:id", {"id": values["id"]})
    )
    asyncio.run(_execute("SELECT pg_sleep(0.01)"))
    asyncio.run(
        _execute(
            "UPDATE requirements SET description=description WHERE id=:id",
            {"id": values["id"]},
        )
    )
    after = asyncio.run(
        _scalar("SELECT updated_at FROM requirements WHERE id=:id", {"id": values["id"]})
    )
    assert after > before

    command.downgrade(_migration_config(), "0010_context_item_review")
    assert asyncio.run(_scalar("SELECT to_regclass('public.requirements') IS NULL")) is True
    command.upgrade(_migration_config(), "head")
    assert asyncio.run(_scalar("SELECT to_regclass('public.requirements') IS NOT NULL")) is True
