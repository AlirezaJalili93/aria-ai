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
from app.modules.sharing.application.change_request_ports import (
    ScopeChangeRequestRepositoryError,
)
from app.modules.sharing.application.public_approval import (
    ApprovePublicScopeCommand,
    ApprovePublicScopeResult,
    PublicScopeApprovalService,
)
from app.modules.sharing.application.public_change_request import (
    PublicScopeChangeRequestService,
    RequestPublicScopeChangesCommand,
    RequestPublicScopeChangesResult,
)
from app.modules.sharing.application.public_decision_errors import (
    PublicScopeAlreadyApproved,
    PublicScopeChangesAlreadyRequested,
)
from app.modules.sharing.application.service import (
    CreateScopeShareLinkCommand,
    ScopeShareLinkService,
)
from app.modules.sharing.domain.scope_change_request import NewScopeChangeRequest
from app.modules.sharing.infrastructure.approval_repository import (
    SqlAlchemyScopeApprovalUnitOfWorkFactory,
)
from app.modules.sharing.infrastructure.change_request_repository import (
    SqlAlchemyScopeChangeRequestUnitOfWorkFactory,
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
    asyncio.run(_execute("TRUNCATE public.accounts RESTART IDENTITY CASCADE"))
    yield


async def _seed() -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id, version_id = (uuid4() for _ in range(4))
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, status, current_context_version) "
        "VALUES (:id, :account, :owner, 'Changes', 'landing', 'awaiting_approval', 1)",
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


async def _services_and_link(
    runtime: DatabaseRuntime,
    user_id: UUID,
    account_id: UUID,
    project_id: UUID,
):
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
    change_service = PublicScopeChangeRequestService(
        SqlAlchemyScopeChangeRequestUnitOfWorkFactory(runtime.session_factory),
        issuer,
        FakeLogger(),  # type: ignore[arg-type]
    )
    with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
        link = await share_service.create(
            _context(user_id, account_id),
            project_id=project_id,
            command=CreateScopeShareLinkCommand(
                version_no=1,
                expires_at=datetime.now(UTC) + timedelta(days=1),
                idempotency_key="create-link",
            ),
        )
    return issuer, approval_service, change_service, link


def test_change_request_and_scope_transition_commit_atomically_and_replay_exactly() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, version_id = asyncio.run(_seed())

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            _, _, service, link = await _services_and_link(
                runtime, user_id, account_id, project_id
            )
            command_model = RequestPublicScopeChangesCommand(
                token=link.public_token,
                guest_name="  A\u0301li رضایی  ",
                comment="  بخش بودجه\r\nاصلاح شود.  ",
                idempotency_key="guest-change",
            )
            first = await service.request_changes(command_model)
            replay = await service.request_changes(command_model)
            return link, first, replay
        finally:
            await runtime.close()

    link, first, replay = asyncio.run(scenario())
    assert first.replayed is False
    assert replay == RequestPublicScopeChangesResult(first.change_request, True)
    row = asyncio.run(
        _execute(
            "SELECT c.*, v.status AS version_status, p.status AS project_status, "
            "l.revoked_at FROM scope_change_requests c "
            "JOIN scope_versions v ON v.id=c.scope_version_id "
            "JOIN projects p ON p.id=c.project_id "
            "JOIN scope_share_links l ON l.id=c.share_link_id WHERE c.id=:id",
            {"id": first.change_request.id},
        )
    ).one()
    assert row.scope_version_id == version_id
    assert row.share_link_id == link.link.id
    assert row.version_hash == "sha256:" + "a" * 64
    assert row.guest_name == "Áli رضایی"
    assert row.comment == "بخش بودجه\nاصلاح شود."
    assert row.version_status == "changes_requested"
    assert row.project_status == "awaiting_approval"
    assert row.revoked_at is None
    assert link.public_token not in repr(row)


def test_approval_and_change_request_race_has_exactly_one_terminal_decision() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, _ = asyncio.run(_seed())

    async def scenario():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            _, approval_service, change_service, link = await _services_and_link(
                runtime, user_id, account_id, project_id
            )
            return await asyncio.gather(
                approval_service.approve(
                    ApprovePublicScopeCommand(
                        token=link.public_token,
                        guest_name="مینا احمدی",
                        explicit_consent=True,
                        idempotency_key="race-approve",
                    )
                ),
                change_service.request_changes(
                    RequestPublicScopeChangesCommand(
                        token=link.public_token,
                        guest_name="مینا احمدی",
                        comment="بخش زمان‌بندی نیاز به اصلاح دارد.",
                        idempotency_key="race-change",
                    )
                ),
                return_exceptions=True,
            )
        finally:
            await runtime.close()

    outcomes = asyncio.run(scenario())
    successes = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, (ApprovePublicScopeResult, RequestPublicScopeChangesResult))
    ]
    failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    assert len(successes) == len(failures) == 1
    if isinstance(successes[0], ApprovePublicScopeResult):
        assert isinstance(failures[0], PublicScopeAlreadyApproved)
        expected_status = "approved"
    else:
        assert isinstance(failures[0], PublicScopeChangesAlreadyRequested)
        expected_status = "changes_requested"

    counts = asyncio.run(
        _execute(
            "SELECT (SELECT count(*) FROM scope_approvals) AS approvals, "
            "(SELECT count(*) FROM scope_change_requests) AS changes, "
            "(SELECT status FROM scope_versions LIMIT 1) AS version_status"
        )
    ).one()
    assert counts.approvals + counts.changes == 1
    assert counts.version_status == expected_status


def test_failure_inside_transaction_rolls_back_change_request_and_scope_state() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, version_id = asyncio.run(_seed())

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            _, _, _, link = await _services_and_link(runtime, user_id, account_id, project_id)
            factory = SqlAlchemyScopeChangeRequestUnitOfWorkFactory(runtime.session_factory)
            with pytest.raises(ScopeChangeRequestRepositoryError):
                async with factory() as unit:
                    await unit.repository.add(
                        NewScopeChangeRequest(
                            id=uuid4(),
                            account_id=account_id,
                            project_id=project_id,
                            scope_version_id=version_id,
                            share_link_id=link.link.id,
                            version_no=1,
                            version_hash="sha256:" + "a" * 64,
                            guest_name="مینا احمدی",
                            comment="اصلاح لازم است.",
                            idempotency_key="rollback",
                            request_hash="b" * 64,
                            requested_at=datetime.now(UTC),
                        )
                    )
                    await unit.repository.mark_scope_version_changes_requested(uuid4())
        finally:
            await runtime.close()

    asyncio.run(scenario())
    state = asyncio.run(
        _execute(
            "SELECT (SELECT count(*) FROM scope_change_requests) AS changes, "
            "(SELECT status FROM scope_versions WHERE id=:id) AS version_status",
            {"id": version_id},
        )
    ).one()
    assert state.changes == 0
    assert state.version_status == "awaiting_approval"


def test_constraints_immutability_rls_and_least_privilege_are_enforced() -> None:
    assert TEST_DATABASE_URL is not None
    user_id, account_id, project_id, _ = asyncio.run(_seed())

    async def create_request():
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            _, _, service, link = await _services_and_link(
                runtime, user_id, account_id, project_id
            )
            return await service.request_changes(
                RequestPublicScopeChangesCommand(
                    token=link.public_token,
                    guest_name="مینا احمدی",
                    comment="اصلاح لازم است.",
                    idempotency_key="immutable",
                )
            )
        finally:
            await runtime.close()

    result = asyncio.run(create_request())
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE scope_change_requests SET comment='changed' WHERE id=:id",
                {"id": result.change_request.id},
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "DELETE FROM scope_change_requests WHERE id=:id",
                {"id": result.change_request.id},
            )
        )

    security = asyncio.run(
        _execute(
            "SELECT c.relrowsecurity, "
            "(SELECT count(*) FROM information_schema.role_table_grants g "
            "WHERE g.table_schema='public' AND g.table_name='scope_change_requests' "
            "AND g.grantee IN ('anon','authenticated')) AS grants, "
            "(SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='scope_change_requests' "
            "AND column_name IN ('token','token_hash','raw_token')) AS secret_columns "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname='scope_change_requests'"
        )
    ).one()
    assert security.relrowsecurity is True
    assert security.grants == 0
    assert security.secret_columns == 0

    async def data_api_probe() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(text("SET LOCAL ROLE authenticated"))
                await connection.execute(text("SELECT id FROM scope_change_requests LIMIT 1"))
        finally:
            await runtime.close()

    with pytest.raises(DBAPIError):
        asyncio.run(data_api_probe())
