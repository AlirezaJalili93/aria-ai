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
from app.modules.sharing.application.public_approval import (
    ApprovePublicScopeCommand,
    PublicScopeAlreadyApproved,
    PublicScopeApprovalNotFound,
    PublicScopeApprovalService,
)
from app.modules.sharing.application.service import (
    CreateScopeShareLinkCommand,
    ScopeShareLinkService,
)
from app.modules.sharing.domain.scope_approval import NewScopeApproval
from app.modules.sharing.infrastructure.approval_repository import (
    SqlAlchemyScopeApprovalUnitOfWorkFactory,
)
from app.modules.sharing.infrastructure.repository import (
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
def clean_schema() -> Iterator[None]:
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
            "TRUNCATE scope_approvals, scope_share_links, scope_versions, scope_drafts, "
            "clarification_resolutions, clarifications, gap_requirement_links, gaps, "
            "requirements, context_items, usage_records, outbox_events, jobs, "
            "idempotency_records, context_source_versions, context_sources, "
            "project_create_requests, projects, account_memberships, profiles, accounts "
            "RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed() -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id, version_id = (uuid4() for _ in range(4))
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, status, current_context_version) "
        "VALUES (:id, :account, :owner, 'Approval', 'landing', 'awaiting_approval', 1)",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO scope_versions "
        "(id, account_id, project_id, version_no, context_version, status, snapshot_data, "
        "snapshot_hash, created_by) VALUES "
        "(:id, :account, :project, 1, 1, 'awaiting_approval', '{}'::jsonb, :hash, :creator)",
        {
            "id": version_id,
            "account": account_id,
            "project": project_id,
            "hash": "sha256:" + "a" * 64,
            "creator": user_id,
        },
    )
    return user_id, account_id, project_id, version_id


def _context(user_id: UUID, account_id: UUID) -> TenantContext:
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def test_approval_and_scope_transition_commit_atomically_and_replay_exactly() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, version_id = asyncio.run(_seed())

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        issuer = SecureScopeShareTokenIssuer()
        share_service = ScopeShareLinkService(
            SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory),
            issuer,
            FakeLogger(),  # type: ignore[arg-type]
        )
        approval_service = PublicScopeApprovalService(
            SqlAlchemyScopeApprovalUnitOfWorkFactory(runtime.session_factory),
            issuer,
            FakeLogger(),  # type: ignore[arg-type]
        )
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                link = await share_service.create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="create-link",
                    ),
                )
                command_model = ApprovePublicScopeCommand(
                    token=link.public_token,
                    guest_name="  A\u0301li رضایی  ",
                    explicit_consent=True,
                    idempotency_key="guest-approval",
                )
                first = await approval_service.approve(command_model)
                replay = await approval_service.approve(command_model)
                with pytest.raises(PublicScopeAlreadyApproved):
                    await approval_service.approve(
                        ApprovePublicScopeCommand(
                            token=link.public_token,
                            guest_name="Áli رضایی",
                            explicit_consent=True,
                            idempotency_key="another-key",
                        )
                    )
                with pytest.raises(PublicScopeApprovalNotFound):
                    await approval_service.approve(
                        ApprovePublicScopeCommand(
                            token=issuer.issue().public_token,
                            guest_name="Áli رضایی",
                            explicit_consent=True,
                            idempotency_key="unknown-token",
                        )
                    )
                return link, first, replay
        finally:
            await runtime.close()

    link, first, replay = asyncio.run(scenario())
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.approval == first.approval

    row = asyncio.run(
        _execute(
            "SELECT a.*, v.status AS version_status, p.status AS project_status "
            "FROM scope_approvals a "
            "JOIN scope_versions v ON v.id=a.scope_version_id "
            "JOIN projects p ON p.id=a.project_id WHERE a.id=:id",
            {"id": first.approval.id},
        )
    ).one()
    assert row.scope_version_id == version_id
    assert row.share_link_id == link.link.id
    assert row.version_no == 1
    assert row.version_hash == "sha256:" + "a" * 64
    assert row.guest_name == "Áli رضایی"
    assert row.explicit_consent is True
    assert row.version_status == "approved"
    assert row.project_status == "awaiting_approval"
    assert link.public_token not in repr(row)


def test_constraints_immutability_rls_and_least_privilege_are_database_enforced() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, _ = asyncio.run(_seed())

    async def create_approval():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        issuer = SecureScopeShareTokenIssuer()
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                link = await ScopeShareLinkService(
                    SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory),
                    issuer,
                    FakeLogger(),  # type: ignore[arg-type]
                ).create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="constraints-link",
                    ),
                )
                return await PublicScopeApprovalService(
                    SqlAlchemyScopeApprovalUnitOfWorkFactory(runtime.session_factory),
                    issuer,
                    FakeLogger(),  # type: ignore[arg-type]
                ).approve(
                    ApprovePublicScopeCommand(
                        token=link.public_token,
                        guest_name="مینا احمدی",
                        explicit_consent=True,
                        idempotency_key="constraints-approval",
                    )
                )
        finally:
            await runtime.close()

    result = asyncio.run(create_approval())
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE scope_approvals SET guest_name='نام دیگر' WHERE id=:id",
                {"id": result.approval.id},
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute("DELETE FROM scope_approvals WHERE id=:id", {"id": result.approval.id})
        )

    catalog = asyncio.run(
        _execute(
            "SELECT c.relrowsecurity, "
            "(SELECT count(*) FROM information_schema.role_table_grants g "
            " WHERE g.table_schema='public' AND g.table_name='scope_approvals' "
            " AND g.grantee IN ('anon','authenticated')) AS data_api_grants, "
            "(SELECT count(*) FROM pg_constraint k "
            " WHERE k.conrelid='public.scope_approvals'::regclass "
            " AND k.contype='f' AND k.confdeltype='r') AS restrict_fks "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname='scope_approvals'"
        )
    ).one()
    assert catalog.relrowsecurity is True
    assert catalog.data_api_grants == 0
    assert catalog.restrict_fks == 4

    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute("SET LOCAL ROLE authenticated; SELECT id FROM scope_approvals LIMIT 1")
        )

    columns = set(
        asyncio.run(
            _execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='scope_approvals'"
            )
        ).scalars()
    )
    assert columns.isdisjoint({"raw_token", "token", "email", "ip", "user_agent"})


def test_concurrent_different_keys_create_one_approval_and_one_loser() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, _ = asyncio.run(_seed())

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        issuer = SecureScopeShareTokenIssuer()
        factory = SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory)
        approval_factory = SqlAlchemyScopeApprovalUnitOfWorkFactory(runtime.session_factory)
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                share_service = ScopeShareLinkService(
                    factory,
                    issuer,
                    FakeLogger(),  # type: ignore[arg-type]
                )
                first_link = await share_service.create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="concurrent-link-1",
                    ),
                )
                second_link = await share_service.create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="concurrent-link-2",
                    ),
                )
            service = PublicScopeApprovalService(
                approval_factory,
                issuer,
                FakeLogger(),  # type: ignore[arg-type]
            )

            async def approve(token: str, name: str, key: str):
                try:
                    return await service.approve(
                        ApprovePublicScopeCommand(
                            token=token,
                            guest_name=name,
                            explicit_consent=True,
                            idempotency_key=key,
                        )
                    )
                except PublicScopeAlreadyApproved as exc:
                    return exc

            return await asyncio.gather(
                approve(first_link.public_token, "مهمان اول", "race-1"),
                approve(second_link.public_token, "مهمان دوم", "race-2"),
            )
        finally:
            await runtime.close()

    outcomes = asyncio.run(scenario())
    assert sum(not isinstance(value, Exception) for value in outcomes) == 1
    assert sum(isinstance(value, PublicScopeAlreadyApproved) for value in outcomes) == 1
    count = asyncio.run(_execute("SELECT count(*) FROM scope_approvals")).scalar_one()
    assert count == 1


def test_uncommitted_approval_and_status_transition_roll_back_together() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, version_id = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        issuer = SecureScopeShareTokenIssuer()
        try:
            with bind_trace_context(
                TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
            ):
                link = await ScopeShareLinkService(
                    SqlAlchemyScopeShareLinkUnitOfWorkFactory(runtime.session_factory),
                    issuer,
                    FakeLogger(),  # type: ignore[arg-type]
                ).create(
                    _context(user_id, account_id),
                    project_id=project_id,
                    command=CreateScopeShareLinkCommand(
                        version_no=1,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        idempotency_key="rollback-link",
                    ),
                )
            factory = SqlAlchemyScopeApprovalUnitOfWorkFactory(runtime.session_factory)
            with pytest.raises(RuntimeError, match="force rollback"):
                async with factory() as unit_of_work:
                    await unit_of_work.repository.add(
                        NewScopeApproval(
                            id=uuid4(),
                            account_id=account_id,
                            project_id=project_id,
                            scope_version_id=version_id,
                            share_link_id=link.link.id,
                            version_no=1,
                            version_hash="sha256:" + "a" * 64,
                            guest_name="مهمان آزمایشی",
                            explicit_consent=True,
                            idempotency_key="rollback-approval",
                            request_hash="b" * 64,
                            approved_at=datetime.now(UTC),
                        )
                    )
                    await unit_of_work.repository.mark_scope_version_approved(version_id)
                    raise RuntimeError("force rollback")
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert asyncio.run(_execute("SELECT count(*) FROM scope_approvals")).scalar_one() == 0
    status_value = asyncio.run(
        _execute("SELECT status FROM scope_versions WHERE id=:id", {"id": version_id})
    ).scalar_one()
    assert status_value == "awaiting_approval"
