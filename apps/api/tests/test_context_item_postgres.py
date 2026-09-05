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
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.context.application.context_item_service import CreateContextItemUseCase
from app.modules.context.domain.context_item import ContextItem, NewContextItem, SourceReference
from app.modules.context.infrastructure.context_item_repository import (
    SqlAlchemyContextItemRepository,
    SqlAlchemyContextItemUnitOfWorkFactory,
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
def clean_context_item_schema() -> Iterator[None]:
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


async def _seed_ready_source() -> tuple[UUID, UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id, source_id, version_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account, :owner, 'Project', 'landing')",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, created_by) "
        "VALUES (:id, :account, :project, 'text', 'ready', :creator)",
        {"id": source_id, "account": account_id, "project": project_id, "creator": user_id},
    )
    await _execute(
        "INSERT INTO context_source_versions "
        "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
        "VALUES (:id, :account, :project, :source, 1, 'متن canonical', 'ready')",
        {"id": version_id, "account": account_id, "project": project_id, "source": source_id},
    )
    return user_id, account_id, project_id, source_id, version_id


CONTEXT_ITEM_INSERT = """
INSERT INTO context_items (
    id, account_id, project_id, context_version, item_type, content, source_refs,
    confidence, status, created_by_type, created_by
) VALUES (
    :id, :account_id, :project_id, :context_version, :item_type, :content,
    CAST(:source_refs AS jsonb), :confidence, :status, :created_by_type, :created_by
)
"""


def _item_values(
    *, user_id: UUID, account_id: UUID, project_id: UUID, source_id: UUID, version_id: UUID
) -> dict[str, object]:
    return {
        "id": uuid4(),
        "account_id": account_id,
        "project_id": project_id,
        "context_version": 1,
        "item_type": "fact",
        "content": "محتوای آیتم",
        "source_refs": json.dumps(
            [{"source_id": str(source_id), "source_version_id": str(version_id)}]
        ),
        "confidence": "0.9000",
        "status": "confirmed",
        "created_by_type": "user",
        "created_by": user_id,
    }


def test_m004_schema_fields_indexes_rls_and_restrictive_foreign_keys() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                schema = await connection.run_sync(
                    lambda sync_connection: (
                        {
                            column["name"]: column
                            for column in inspect(sync_connection).get_columns("context_items")
                        },
                        {
                            index["name"]
                            for index in inspect(sync_connection).get_indexes("context_items")
                        },
                        {
                            fk["name"]: fk.get("options", {}).get("ondelete")
                            for fk in inspect(sync_connection).get_foreign_keys("context_items")
                        },
                    )
                )
                rls = (
                    await connection.execute(
                        text(
                            "SELECT relrowsecurity FROM pg_catalog.pg_class "
                            "WHERE oid='public.context_items'::regclass"
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
        "item_type",
        "content",
        "source_refs",
        "confidence",
        "status",
        "created_by_type",
        "created_by",
        "created_at",
    }
    assert columns["confidence"]["type"].precision == 5
    assert columns["confidence"]["type"].scale == 4
    assert {
        "ix_context_items_account_project_version",
        "ix_context_items_created_by",
    }.issubset(indexes)
    assert foreign_keys == {
        "fk_context_items_account_id_accounts": "RESTRICT",
        "fk_context_items_project_id_account_id_projects": "RESTRICT",
        "fk_context_items_created_by_profiles": "RESTRICT",
    }
    assert rls is True


def test_database_accepts_canonical_row_and_preserves_content() -> None:
    user_id, account_id, project_id, source_id, version_id = asyncio.run(_seed_ready_source())
    values = _item_values(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_id=version_id,
    )
    values["content"] = "  متن بدون نرمال‌سازی  "
    asyncio.run(_execute(CONTEXT_ITEM_INSERT, values))
    assert asyncio.run(
        _scalar("SELECT content FROM context_items WHERE id=:id", {"id": values["id"]})
    ) == values["content"]


def test_database_defaults_to_proposed_and_allows_empty_non_fact_provenance() -> None:
    user_id, account_id, project_id, _, _ = asyncio.run(_seed_ready_source())
    item_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO context_items "
            "(id, account_id, project_id, context_version, item_type, content, source_refs, "
            "created_by_type, created_by) "
            "VALUES (:id, :account, :project, 1, 'assumption', '', '[]'::jsonb, "
            "'user', :creator)",
            {
                "id": item_id,
                "account": account_id,
                "project": project_id,
                "creator": user_id,
            },
        )
    )
    assert asyncio.run(
        _scalar("SELECT status FROM context_items WHERE id=:id", {"id": item_id})
    ) == "proposed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_version", 0),
        ("item_type", "claim"),
        ("status", "active"),
        ("created_by_type", "human"),
        ("confidence", "-0.0001"),
        ("confidence", "1.0001"),
        ("source_refs", "{}"),
    ],
)
def test_database_rejects_invalid_contract_values(field: str, value: object) -> None:
    user_id, account_id, project_id, source_id, version_id = asyncio.run(_seed_ready_source())
    values = _item_values(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_id=version_id,
    )
    values[field] = value
    with pytest.raises(IntegrityError):
        asyncio.run(_execute(CONTEXT_ITEM_INSERT, values))


def test_database_requires_creator_for_user_and_evidence_for_confirmed_fact() -> None:
    user_id, account_id, project_id, source_id, version_id = asyncio.run(_seed_ready_source())
    values = _item_values(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_id=version_id,
    )
    for overrides in (
        {"created_by": None},
        {"source_refs": "[]"},
    ):
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(CONTEXT_ITEM_INSERT, {**values, **overrides, "id": uuid4()}))


def test_database_rejects_cross_tenant_project_and_restricts_parent_deletes() -> None:
    user_id, account_id, project_id, source_id, version_id = asyncio.run(_seed_ready_source())
    _, _, other_project_id, _, _ = asyncio.run(_seed_ready_source())
    values = _item_values(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_id=version_id,
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(CONTEXT_ITEM_INSERT, {**values, "id": uuid4(), "project_id": other_project_id})
        )

    asyncio.run(_execute(CONTEXT_ITEM_INSERT, values))
    for statement, identifier in (
        ("DELETE FROM profiles WHERE user_id=:id", user_id),
        ("DELETE FROM projects WHERE id=:id", project_id),
        ("DELETE FROM accounts WHERE id=:id", account_id),
    ):
        with pytest.raises(IntegrityError):
            asyncio.run(_execute(statement, {"id": identifier}))


def test_data_api_roles_have_no_context_item_privileges() -> None:
    assert asyncio.run(
        _scalar(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE table_schema='public' AND table_name='context_items' "
            "AND grantee IN ('anon','authenticated')"
        )
    ) == 0


def test_repository_resolves_only_same_tenant_ready_source_version() -> None:
    user_id, account_id, project_id, source_id, version_id = asyncio.run(_seed_ready_source())
    assert TEST_DATABASE_URL is not None
    pending_version_id, other_source_id = uuid4(), uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO context_source_versions "
            "(id, account_id, project_id, source_id, version_no, parse_status) "
            "VALUES (:id, :account, :project, :source, 2, 'pending')",
            {
                "id": pending_version_id,
                "account": account_id,
                "project": project_id,
                "source": source_id,
            },
        )
    )
    asyncio.run(
        _execute(
            "INSERT INTO context_sources "
            "(id, account_id, project_id, source_type, status, created_by) "
            "VALUES (:id, :account, :project, 'text', 'ready', :creator)",
            {
                "id": other_source_id,
                "account": account_id,
                "project": project_id,
                "creator": user_id,
            },
        )
    )

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.session_factory() as session:
                repository = SqlAlchemyContextItemRepository(session)
                valid = await repository.resolve_provenance(
                    account_id=account_id,
                    project_id=project_id,
                    source_id=source_id,
                    source_version_id=version_id,
                )
                cross_tenant = await repository.resolve_provenance(
                    account_id=uuid4(),
                    project_id=project_id,
                    source_id=source_id,
                    source_version_id=version_id,
                )
                pending = await repository.resolve_provenance(
                    account_id=account_id,
                    project_id=project_id,
                    source_id=source_id,
                    source_version_id=pending_version_id,
                )
                mismatched = await repository.resolve_provenance(
                    account_id=account_id,
                    project_id=project_id,
                    source_id=other_source_id,
                    source_version_id=version_id,
                )
                return valid, cross_tenant, pending, mismatched
        finally:
            await runtime.close()

    valid, cross_tenant, pending, mismatched = asyncio.run(scenario())
    assert valid is not None
    assert valid.canonical_text_length == len("متن canonical")
    assert cross_tenant is None
    assert pending is None
    assert mismatched is None


def test_validated_use_case_persists_exact_source_reference_json() -> None:
    _, account_id, project_id, source_id, version_id = asyncio.run(_seed_ready_source())
    assert TEST_DATABASE_URL is not None
    item_id = uuid4()

    async def scenario() -> tuple[ContextItem, object]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            service = CreateContextItemUseCase(
                SqlAlchemyContextItemUnitOfWorkFactory(runtime.session_factory)
            )
            persisted = await service.execute(
                NewContextItem(
                    id=item_id,
                    account_id=account_id,
                    project_id=project_id,
                    context_version=1,
                    item_type="fact",
                    content="محتوای محرمانه",
                    source_refs=(SourceReference(source_id, version_id, 0, 3),),
                    confidence=None,
                    status="confirmed",
                    created_by_type="ai",
                    created_by=None,
                )
            )
            async with runtime.engine.connect() as connection:
                source_refs = (
                    await connection.execute(
                        text("SELECT source_refs FROM context_items WHERE id=:id"), {"id": item_id}
                    )
                ).scalar_one()
            return persisted, source_refs
        finally:
            await runtime.close()

    persisted, source_refs = asyncio.run(scenario())
    assert persisted.id == item_id
    assert source_refs == [
        {
            "source_id": str(source_id),
            "source_version_id": str(version_id),
            "start_offset": 0,
            "end_offset": 3,
        }
    ]


def test_context_item_migration_downgrades_and_reupgrades() -> None:
    command.downgrade(_migration_config(), "0007_usage_records")
    assert asyncio.run(_scalar("SELECT to_regclass('public.context_items') IS NULL")) is True
    command.upgrade(_migration_config(), "head")
    assert asyncio.run(_scalar("SELECT to_regclass('public.context_items') IS NOT NULL")) is True
