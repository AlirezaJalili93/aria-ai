from __future__ import annotations

import asyncio
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
from app.modules.sharing.application.ports import (
    IssuedScopeShareToken,
    ScopeShareLinkRepositoryError,
)
from app.modules.sharing.application.public_resolver import (
    PublicScopeShareNotFound,
    PublicScopeShareResolver,
)
from app.modules.sharing.application.service import (
    CreateScopeShareLinkCommand,
    RevokeScopeShareLinkCommand,
    ScopeShareLinkAccessNotFound,
    ScopeShareLinkService,
)
from app.modules.sharing.infrastructure.repository import (
    SqlAlchemyScopeShareLinkRepository,
    SqlAlchemyScopeShareLinkUnitOfWorkFactory,
)
from app.modules.sharing.infrastructure.tokens import SecureScopeShareTokenIssuer

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
def clean_share_link_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    asyncio.run(
        _execute(
            "DO $aria$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN "
            "CREATE ROLE anon NOLOGIN; END IF; "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN "
            "CREATE ROLE authenticated NOLOGIN; END IF; END $aria$"
        )
    )
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE scope_change_requests, scope_approvals, scope_share_links, "
            "scope_versions, scope_drafts, "
            "clarification_resolutions, clarifications, gap_requirement_links, gaps, "
            "requirements, context_items, usage_records, outbox_events, jobs, "
            "idempotency_records, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed() -> tuple[UUID, UUID, UUID, UUID, UUID, UUID, UUID]:
    user_a, user_b = uuid4(), uuid4()
    account_a, account_b = uuid4(), uuid4()
    project_a, project_b = uuid4(), uuid4()
    version_a = uuid4()
    await _execute(
        "INSERT INTO profiles (user_id) VALUES (:user_a), (:user_b)",
        {"user_a": user_a, "user_b": user_b},
    )
    await _execute(
        "INSERT INTO accounts (id) VALUES (:account_a), (:account_b)",
        {"account_a": account_a, "account_b": account_b},
    )
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) VALUES "
        "(:project_a, :account_a, :user_a, 'A', 'landing', 1), "
        "(:project_b, :account_b, :user_b, 'B', 'corporate', 1)",
        {
            "project_a": project_a,
            "project_b": project_b,
            "account_a": account_a,
            "account_b": account_b,
            "user_a": user_a,
            "user_b": user_b,
        },
    )
    await _execute(
        "INSERT INTO scope_versions "
        "(id, account_id, project_id, version_no, context_version, status, snapshot_data, "
        "snapshot_hash, created_by) VALUES "
        "(:id, :account, :project, 1, 1, 'awaiting_approval', '{}'::jsonb, :hash, :creator)",
        {
            "id": version_a,
            "account": account_a,
            "project": project_a,
            "hash": "sha256:" + "a" * 64,
            "creator": user_a,
        },
    )
    return user_a, user_b, account_a, account_b, project_a, project_b, version_a


def _context(user_id: UUID, account_id: UUID, *, role="member") -> TenantContext:
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=uuid4(),
        role=role,
        membership_status="active",
    )


def test_create_revoke_safe_not_found_and_hash_only_persistence() -> None:
    assert TEST_DATABASE_URL is not None
    user_a, user_b, account_a, account_b, project_a, _, version_a = asyncio.run(_seed())

    async def scenario() -> tuple[UUID, str]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeShareLinkService(
            SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory),
            SecureScopeShareTokenIssuer(),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                created = await service.create(
                    _context(user_a, account_a),
                    project_id=project_a,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="create-a",
                    ),
                )
                with pytest.raises(ScopeShareLinkAccessNotFound):
                    await service.create(
                        _context(user_b, account_b),
                        project_id=project_a,
                        command=CreateScopeShareLinkCommand(
                            version_no=1,
                            expires_at=datetime.now(UTC) + timedelta(days=1),
                            idempotency_key="foreign-create",
                        ),
                    )
                with pytest.raises(ScopeShareLinkAccessNotFound):
                    await service.revoke(
                        _context(user_b, account_a),
                        project_id=project_a,
                        share_link_id=created.link.id,
                        command=RevokeScopeShareLinkCommand(idempotency_key="member-denied"),
                    )
                revoked = await service.revoke(
                    _context(user_b, account_a, role="admin"),
                    project_id=project_a,
                    share_link_id=created.link.id,
                    command=RevokeScopeShareLinkCommand(idempotency_key="admin-revoke"),
                )
                replay = await service.revoke(
                    _context(user_b, account_a, role="admin"),
                    project_id=project_a,
                    share_link_id=created.link.id,
                    command=RevokeScopeShareLinkCommand(idempotency_key="admin-revoke"),
                )
                assert replay == revoked
                return created.link.id, created.public_token
        finally:
            await runtime.close()

    share_link_id, public_token = asyncio.run(scenario())
    row = asyncio.run(
        _execute(
            "SELECT token_hash, revoked_at FROM scope_share_links WHERE id=:id",
            {"id": share_link_id},
        )
    ).one()
    assert bytes(row.token_hash) == SecureScopeShareTokenIssuer.hash_public_token(public_token)
    assert public_token.encode("utf-8") not in bytes(row.token_hash)
    assert row.revoked_at is not None

    columns = asyncio.run(
        _execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='scope_share_links'"
        )
    ).scalars()
    assert set(columns).isdisjoint({"raw_token", "public_token", "snapshot_data", "content"})


def test_database_constraints_rls_restrict_and_terminal_revocation() -> None:
    user_a, _, account_a, account_b, project_a, project_b, version_a = asyncio.run(_seed())
    link_id = uuid4()
    token_hash = b"z" * 32
    awaitable_insert = (
        "INSERT INTO scope_share_links "
        "(id, account_id, project_id, scope_version_id, token_hash, expires_at, created_by) "
        "VALUES (:id, :account, :project, :version, :hash, now() + interval '1 day', :creator)"
    )
    asyncio.run(
        _execute(
            awaitable_insert,
            {
                "id": link_id,
                "account": account_a,
                "project": project_a,
                "version": version_a,
                "hash": token_hash,
                "creator": user_a,
            },
        )
    )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                awaitable_insert,
                {
                    "id": uuid4(),
                    "account": account_a,
                    "project": project_a,
                    "version": version_a,
                    "hash": token_hash,
                    "creator": user_a,
                },
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                awaitable_insert,
                {
                    "id": uuid4(),
                    "account": account_b,
                    "project": project_b,
                    "version": version_a,
                    "hash": b"y" * 32,
                    "creator": user_a,
                },
            )
        )

    asyncio.run(
        _execute("UPDATE scope_share_links SET revoked_at=now() WHERE id=:id", {"id": link_id})
    )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute("UPDATE scope_share_links SET revoked_at=NULL WHERE id=:id", {"id": link_id})
        )
    with pytest.raises(DBAPIError):
        asyncio.run(_execute("DELETE FROM scope_share_links WHERE id=:id", {"id": link_id}))

    catalog = asyncio.run(
        _execute(
            "SELECT c.relrowsecurity, "
            "(SELECT count(*) FROM information_schema.role_table_grants g "
            " WHERE g.table_schema='public' AND g.table_name='scope_share_links' "
            " AND g.grantee IN ('anon','authenticated')) AS data_api_grants, "
            "(SELECT count(*) FROM pg_constraint k "
            " WHERE k.conrelid='public.scope_share_links'::regclass "
            " AND k.contype='f' AND k.confdeltype='r') AS restrict_fks "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname='scope_share_links'"
        )
    ).one()
    assert catalog.relrowsecurity is True
    assert catalog.data_api_grants == 0
    assert catalog.restrict_fks == 4

    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute("SET LOCAL ROLE authenticated; SELECT id FROM scope_share_links LIMIT 1")
        )


def test_public_resolution_is_exact_version_and_fails_closed_for_all_inactive_states() -> None:
    assert TEST_DATABASE_URL is not None
    user_a, _, account_a, _, project_a, _, version_a = asyncio.run(_seed())
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        factory = SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory)
        issuer = SecureScopeShareTokenIssuer()
        service = ScopeShareLinkService(factory, issuer, FakeLogger())  # type: ignore[arg-type]
        resolver = PublicScopeShareResolver(factory, issuer, FakeLogger())  # type: ignore[arg-type]
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                created = await service.create(
                    _context(user_a, account_a),
                    project_id=project_a,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=expires_at,
                        idempotency_key="public-resolution",
                    ),
                )
                await _execute(
                    "INSERT INTO scope_versions "
                    "(id, account_id, project_id, version_no, context_version, status, "
                    "snapshot_data, snapshot_hash, created_by) VALUES "
                    "(:id, :account, :project, 2, 1, 'awaiting_approval', "
                    "'{\"newer\": true}'::jsonb, :hash, :creator)",
                    {
                        "id": uuid4(),
                        "account": account_a,
                        "project": project_a,
                        "hash": "sha256:" + "b" * 64,
                        "creator": user_a,
                    },
                )

                resolved = await resolver.resolve(token=created.public_token)
                assert resolved.scope_version_id == version_a
                assert resolved.version_no == 1
                assert resolved.snapshot_data == {}

                unknown = issuer.issue().public_token
                with pytest.raises(PublicScopeShareNotFound):
                    await resolver.resolve(token=unknown)

                expired_resolver = PublicScopeShareResolver(
                    factory,
                    issuer,
                    FakeLogger(),  # type: ignore[arg-type]
                    clock=lambda: expires_at,
                )
                with pytest.raises(PublicScopeShareNotFound):
                    await expired_resolver.resolve(token=created.public_token)

                await service.revoke(
                    _context(user_a, account_a),
                    project_id=project_a,
                    share_link_id=created.link.id,
                    command=RevokeScopeShareLinkCommand(idempotency_key="public-revoke"),
                )
                with pytest.raises(PublicScopeShareNotFound):
                    await resolver.resolve(token=created.public_token)

                inaccessible = await service.create(
                    _context(user_a, account_a),
                    project_id=project_a,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="inaccessible-create",
                    ),
                )
                await _execute(
                    "UPDATE projects SET deleted_at=now() WHERE id=:project_id",
                    {"project_id": project_a},
                )
                with pytest.raises(PublicScopeShareNotFound):
                    await resolver.resolve(token=inaccessible.public_token)
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_public_resolve_shared_lock_serializes_with_revocation() -> None:
    assert TEST_DATABASE_URL is not None
    user_a, _, account_a, _, project_a, _, version_a = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        factory = SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory)
        issuer = SecureScopeShareTokenIssuer()
        service = ScopeShareLinkService(factory, issuer, FakeLogger())  # type: ignore[arg-type]
        session_resolve = runtime.session_factory()
        session_revoke = runtime.session_factory()
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                created = await service.create(
                    _context(user_a, account_a),
                    project_id=project_a,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="locking-create",
                    ),
                )

                resolve_repository = SqlAlchemyScopeShareLinkRepository(session_resolve)
                revoke_repository = SqlAlchemyScopeShareLinkRepository(session_revoke)
                resolved = await resolve_repository.resolve_public(
                    token_hash=created.link.token_hash,
                    now=datetime.now(UTC),
                )
                assert resolved is not None

                await session_revoke.execute(text("SET LOCAL lock_timeout = '100ms'"))
                with pytest.raises(DBAPIError):
                    await revoke_repository.get_for_update(
                        account_id=account_a,
                        project_id=project_a,
                        share_link_id=created.link.id,
                    )
                await session_revoke.rollback()

                await session_resolve.rollback()
                locked = await revoke_repository.get_for_update(
                    account_id=account_a,
                    project_id=project_a,
                    share_link_id=created.link.id,
                )
                assert locked is not None
                await revoke_repository.set_revoked(locked.revoke(now=datetime.now(UTC)))
                await session_revoke.commit()

                resolver = PublicScopeShareResolver(factory, issuer, FakeLogger())  # type: ignore[arg-type]
                with pytest.raises(PublicScopeShareNotFound):
                    await resolver.resolve(token=created.public_token)
        finally:
            await session_resolve.close()
            await session_revoke.close()
            await runtime.close()

    asyncio.run(scenario())


def test_concurrent_same_key_creates_one_link_and_discloses_one_token() -> None:
    assert TEST_DATABASE_URL is not None
    user_a, _, account_a, _, project_a, _, _ = asyncio.run(_seed())
    expires_at = datetime.now(UTC) + timedelta(days=1)

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeShareLinkService(
            SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory),
            SecureScopeShareTokenIssuer(),
            FakeLogger(),  # type: ignore[arg-type]
        )
        command = CreateScopeShareLinkCommand(
            version_no=1,
            expires_at=expires_at,
            idempotency_key="concurrent-create",
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                return await asyncio.gather(
                    service.create(
                        _context(user_a, account_a), project_id=project_a, command=command
                    ),
                    service.create(
                        _context(user_a, account_a), project_id=project_a, command=command
                    ),
                )
        finally:
            await runtime.close()

    first, second = asyncio.run(scenario())
    assert first.link.id == second.link.id
    assert sorted([first.token_available, second.token_available]) == [False, True]
    assert sum(result.public_token is not None for result in (first, second)) == 1
    assert int(asyncio.run(_execute("SELECT count(*) FROM scope_share_links")).scalar_one()) == 1
    record = asyncio.run(
        _execute(
            "SELECT response_ref::text AS response_ref FROM idempotency_records "
            "WHERE idempotency_key='concurrent-create'"
        )
    ).one()
    assert "scope_share_link_id" in record.response_ref
    assert "token" not in record.response_ref


def test_link_constraint_failure_rolls_back_idempotency_reservation() -> None:
    assert TEST_DATABASE_URL is not None
    user_a, _, account_a, _, project_a, _, version_a = asyncio.run(_seed())
    asyncio.run(
        _execute(
            "INSERT INTO scope_share_links "
            "(id, account_id, project_id, scope_version_id, token_hash, expires_at, created_by) "
            "VALUES (:id, :account, :project, :version, :hash, "
            "now() + interval '1 day', :creator)",
            {
                "id": uuid4(),
                "account": account_a,
                "project": project_a,
                "version": version_a,
                "hash": b"d" * 32,
                "creator": user_a,
            },
        )
    )

    class DuplicateHashIssuer:
        def issue(self) -> IssuedScopeShareToken:
            return IssuedScopeShareToken(public_token="discarded-token", token_hash=b"d" * 32)

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = ScopeShareLinkService(
            SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory),
            DuplicateHashIssuer(),
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ), pytest.raises(ScopeShareLinkRepositoryError):
                await service.create(
                    _context(user_a, account_a),
                    project_id=project_a,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="rolled-back-create",
                    ),
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert int(
        asyncio.run(
            _execute(
                "SELECT count(*) FROM idempotency_records "
                "WHERE idempotency_key='rolled-back-create'"
            )
        ).scalar_one()
    ) == 0
    assert int(asyncio.run(_execute("SELECT count(*) FROM scope_share_links")).scalar_one()) == 1
