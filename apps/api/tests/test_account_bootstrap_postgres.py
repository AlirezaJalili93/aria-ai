from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.identity.application.account_bootstrap import (
    ActiveMembershipRequired,
    BootstrapAccountUseCase,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.infrastructure.account_bootstrap import (
    SqlAlchemyAccountBootstrapUnitOfWorkFactory,
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
def clean_identity_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute("TRUNCATE account_memberships, profiles, accounts RESTART IDENTITY CASCADE")
    )
    yield


def test_m001_schema_enforces_profile_and_membership_contract() -> None:
    assert TEST_DATABASE_URL is not None

    async def inspect_schema() -> tuple[set[str], set[str], set[str], set[str], set[str]]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: (
                        {item["name"] for item in inspect(sync_connection).get_columns("profiles")},
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_check_constraints(
                                "account_memberships"
                            )
                        },
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_unique_constraints(
                                "account_memberships"
                            )
                        },
                        {
                            item["name"]
                            for item in inspect(sync_connection).get_indexes("account_memberships")
                        },
                        set(
                            sync_connection.execute(
                                text(
                                    """
                                    SELECT relname
                                    FROM pg_class
                                    WHERE relname IN ('accounts','profiles','account_memberships')
                                      AND relrowsecurity = true
                                    """
                                )
                            ).scalars()
                        ),
                    )
                )
        finally:
            await runtime.close()

    profile_columns, checks, unique_constraints, indexes, rls_tables = asyncio.run(
        inspect_schema()
    )
    assert profile_columns == {
        "user_id",
        "display_name",
        "locale",
        "profile_data",
        "created_at",
        "updated_at",
    }
    assert "email" not in profile_columns
    assert "ck_account_memberships_membership_role" in checks
    assert "ck_account_memberships_membership_status" in checks
    assert "uq_account_memberships_account_id_user_id" in unique_constraints
    assert indexes >= {
        "ix_account_memberships_user_id_status",
        "ix_account_memberships_account_id_status",
    }
    assert rls_tables == {"accounts", "profiles", "account_memberships"}

    subject = uuid4()
    asyncio.run(_execute("INSERT INTO profiles (user_id) VALUES (:user_id)", {"user_id": subject}))
    locale = asyncio.run(
        _scalar("SELECT locale FROM profiles WHERE user_id = :user_id", {"user_id": subject})
    )
    assert locale == "fa-IR"

    account_id = asyncio.run(
        _scalar("INSERT INTO accounts DEFAULT VALUES RETURNING id")
    )
    with pytest.raises(IntegrityError):
        asyncio.run(
            _execute(
                """
                INSERT INTO account_memberships (id, account_id, user_id, role, status)
                VALUES (:id, :account_id, :user_id, 'owner', 'disabled')
                """,
                {"id": uuid4(), "account_id": account_id, "user_id": subject},
            )
        )


def test_first_and_repeated_bootstrap_preserve_rows_without_rewrite() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        use_case = BootstrapAccountUseCase(
            SqlAlchemyAccountBootstrapUnitOfWorkFactory(runtime.session_factory)
        )
        subject = uuid4()
        try:
            first = await use_case.execute(AuthenticatedIdentity(subject=subject))
            before = await _scalar(
                """
                SELECT p.xmin::text || ':' || a.xmin::text || ':' || m.xmin::text
                FROM profiles p
                JOIN account_memberships m ON m.user_id = p.user_id
                JOIN accounts a ON a.id = m.account_id
                WHERE p.user_id = :user_id
                """,
                {"user_id": subject},
            )
            second = await use_case.execute(AuthenticatedIdentity(subject=subject))
            after = await _scalar(
                """
                SELECT p.xmin::text || ':' || a.xmin::text || ':' || m.xmin::text
                FROM profiles p
                JOIN account_memberships m ON m.user_id = p.user_id
                JOIN accounts a ON a.id = m.account_id
                WHERE p.user_id = :user_id
                """,
                {"user_id": subject},
            )
        finally:
            await runtime.close()

        assert first.created is True
        assert second.created is False
        assert second.active_memberships == first.active_memberships
        assert before == after

    asyncio.run(scenario())


def test_two_concurrent_bootstraps_create_one_projection_aggregate() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        use_case = BootstrapAccountUseCase(
            SqlAlchemyAccountBootstrapUnitOfWorkFactory(runtime.session_factory)
        )
        subject = uuid4()
        try:
            first, second = await asyncio.gather(
                use_case.execute(AuthenticatedIdentity(subject=subject)),
                use_case.execute(AuthenticatedIdentity(subject=subject)),
            )
        finally:
            await runtime.close()

        assert sorted((first.created, second.created)) == [False, True]
        assert await _scalar("SELECT count(*) FROM profiles") == 1
        assert await _scalar("SELECT count(*) FROM accounts") == 1
        assert await _scalar("SELECT count(*) FROM account_memberships") == 1

    asyncio.run(scenario())


def test_commit_failure_rolls_back_profile_account_and_membership() -> None:
    assert TEST_DATABASE_URL is not None
    duplicate_account_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO accounts (id) VALUES (:account_id)",
            {"account_id": duplicate_account_id},
        )
    )
    generated_ids = iter((duplicate_account_id, uuid4()))
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    use_case = BootstrapAccountUseCase(
        SqlAlchemyAccountBootstrapUnitOfWorkFactory(runtime.session_factory),
        id_factory=lambda: next(generated_ids),
    )
    subject = uuid4()

    async def execute_and_close() -> None:
        try:
            await use_case.execute(AuthenticatedIdentity(subject=subject))
        finally:
            await runtime.close()

    with pytest.raises(IntegrityError):
        asyncio.run(execute_and_close())

    assert asyncio.run(_scalar("SELECT count(*) FROM profiles")) == 0
    assert asyncio.run(_scalar("SELECT count(*) FROM accounts")) == 1
    assert asyncio.run(_scalar("SELECT count(*) FROM account_memberships")) == 0


def test_suspended_membership_denies_context_without_deleting_membership() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        use_case = BootstrapAccountUseCase(
            SqlAlchemyAccountBootstrapUnitOfWorkFactory(runtime.session_factory)
        )
        subject = uuid4()
        try:
            await use_case.execute(AuthenticatedIdentity(subject=subject))
            await _execute(
                "UPDATE account_memberships SET status = 'suspended' WHERE user_id = :user_id",
                {"user_id": subject},
            )
            with pytest.raises(ActiveMembershipRequired):
                await use_case.execute(AuthenticatedIdentity(subject=subject))
        finally:
            await runtime.close()

        assert (
            await _scalar(
                "SELECT status FROM account_memberships WHERE user_id = :user_id",
                {"user_id": subject},
            )
            == "suspended"
        )
        assert await _scalar("SELECT count(*) FROM account_memberships") == 1

    asyncio.run(scenario())


def test_identity_revision_downgrades_and_reapplies_cleanly() -> None:
    assert TEST_DATABASE_URL is not None
    config = _migration_config()
    command.downgrade(config, "0000_extensions")

    async def table_names() -> set[str]:
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: set(inspect(sync_connection).get_table_names())
                )
        finally:
            await runtime.close()

    assert not {"accounts", "profiles", "account_memberships"} & asyncio.run(table_names())
    command.upgrade(config, "head")
    assert {"accounts", "profiles", "account_memberships"} <= asyncio.run(table_names())


def test_identity_access_hardening_revokes_data_api_roles() -> None:
    config = _migration_config()
    command.downgrade(config, "0001_identity_projection")

    async def prepare_supabase_roles() -> None:
        await _execute(
            """
            DO $aria$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    CREATE ROLE anon NOLOGIN;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'authenticated'
                ) THEN
                    CREATE ROLE authenticated NOLOGIN;
                END IF;
            END
            $aria$;
            """
        )
        for role in ("anon", "authenticated"):
            await _execute(
                "GRANT ALL PRIVILEGES ON TABLE accounts, profiles, "
                f"account_memberships, alembic_version TO {role}"
            )
            await _execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT ALL PRIVILEGES ON TABLES TO {role}"
            )

    asyncio.run(prepare_supabase_roles())
    command.upgrade(config, "head")

    assert asyncio.run(
        _scalar(
            """
            SELECT relrowsecurity
            FROM pg_catalog.pg_class
            WHERE oid = 'public.alembic_version'::regclass
            """
        )
    )
    assert (
        asyncio.run(
            _scalar(
                """
                SELECT count(*)
                FROM information_schema.role_table_grants
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'accounts', 'profiles', 'account_memberships', 'alembic_version'
                  )
                  AND grantee IN ('anon', 'authenticated')
                """
            )
        )
        == 0
    )
    assert (
        asyncio.run(
            _scalar(
                """
                SELECT count(*)
                FROM pg_catalog.pg_default_acl AS defaults
                CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) AS acl
                JOIN pg_catalog.pg_roles AS roles ON roles.oid = acl.grantee
                WHERE defaults.defaclnamespace = 'public'::regnamespace
                  AND defaults.defaclobjtype = 'r'
                  AND roles.rolname IN ('anon', 'authenticated')
                """
            )
        )
        == 0
    )
