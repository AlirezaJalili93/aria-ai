"""Guarded 0040 downgrade and cluster Role preservation on disposable PostgreSQL."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from test_artifact_foundation_postgres import TEST_DATABASE_URL
from test_artifact_foundation_postgres import (
    clean_artifact_schema as clean_artifact_schema,
)
from test_preview_authority_postgres import allocated, claim, engine

pytestmark = pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Throwaway PostgreSQL required")
CONFIG = Path(__file__).parents[1] / "alembic.ini"
PREVIOUS = "0039_artifact_generation_runtime"


async def scalar(sql: str, *, url: str | None = None):
    assert TEST_DATABASE_URL is not None
    db = create_async_engine(url or TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with db.begin() as conn:
            result = await conn.execute(text(sql))
            return result.scalar() if result.returns_rows else None
    finally:
        await db.dispose()


@pytest.mark.parametrize("with_claim", [False, True])
def test_nonempty_downgrade_preserves_rows_functions_and_revision(with_claim: bool) -> None:
    binding = asyncio.run(allocated())

    async def own_claim() -> None:
        worker = engine(worker=True)
        try:
            async with worker.connect() as conn, conn.begin():
                await claim(conn, binding)
            # Closing session releases its advisory lock; the persisted claim remains.
        finally:
            await worker.dispose()

    if with_claim:
        asyncio.run(own_claim())
    before = asyncio.run(scalar("SELECT count(*) FROM public.preview_publications"))
    with pytest.raises(Exception, match="Preview downgrade denied: state exists"):
        command.downgrade(Config(str(CONFIG)), PREVIOUS)
    assert asyncio.run(scalar("SELECT count(*) FROM public.preview_publications")) == before
    assert (
        asyncio.run(scalar("SELECT version_num FROM alembic_version")) == "0041_preview_failure"
    )
    assert asyncio.run(
        scalar("SELECT to_regprocedure('aria_internal.claim_preview(uuid,uuid)') IS NOT NULL")
    )


def test_empty_downgrade_and_reupgrade_restore_four_helpers() -> None:
    config = Config(str(CONFIG))
    command.downgrade(config, PREVIOUS)
    assert asyncio.run(scalar("SELECT to_regclass('public.preview_publications') IS NULL"))
    assert (
        asyncio.run(
            scalar("SELECT count(*) FROM pg_roles WHERE rolname='aria_preview_runtime_owner'")
        )
        == 0
    )
    command.upgrade(config, "head")
    assert (
        asyncio.run(
            scalar(
                "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='aria_internal' AND p.proname IN "
                "('claim_preview','finalize_preview','release_preview','resolve_preview')"
            )
        )
        == 4
    )


def test_incompatible_preserved_role_fails_closed_and_rolls_back_schema() -> None:
    config = Config(str(CONFIG))
    command.downgrade(config, PREVIOUS)
    asyncio.run(
        scalar(
            "CREATE ROLE aria_preview_runtime_owner LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS "
            "NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
    )
    try:
        with pytest.raises(RuntimeError, match="Preview runtime owner attributes rejected"):
            command.upgrade(config, "head")
        assert asyncio.run(scalar("SELECT to_regclass('public.preview_publications') IS NULL"))
        assert asyncio.run(scalar("SELECT version_num FROM alembic_version")) == PREVIOUS
        assert asyncio.run(
            scalar("SELECT rolcanlogin FROM pg_roles WHERE rolname='aria_preview_runtime_owner'")
        )
    finally:
        asyncio.run(scalar("DROP ROLE aria_preview_runtime_owner"))
        command.upgrade(config, "head")


def test_downgrade_preserves_role_and_helpers_in_other_database_and_reuses_safe_role() -> None:
    assert TEST_DATABASE_URL is not None
    database = "aria_0102_role_" + uuid4().hex
    current_url = make_url(TEST_DATABASE_URL)
    other_url = current_url.set(database=database).render_as_string(hide_password=False)
    original_env = os.environ.get("DATABASE_URL")
    created = False

    async def database_command(sql: str) -> None:
        db = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with db.connect() as conn:
                conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
                await conn.execute(text(sql))
        finally:
            await db.dispose()

    try:
        asyncio.run(database_command(f'CREATE DATABASE "{database}"'))
        created = True
        os.environ["DATABASE_URL"] = other_url
        command.upgrade(Config(str(CONFIG)), "head")
        os.environ["DATABASE_URL"] = TEST_DATABASE_URL
        command.downgrade(Config(str(CONFIG)), PREVIOUS)
        assert (
            asyncio.run(
                scalar("SELECT count(*) FROM pg_roles WHERE rolname='aria_preview_runtime_owner'")
            )
            == 1
        )
        assert asyncio.run(
            scalar(
                "SELECT to_regprocedure('aria_internal.resolve_preview(text)') IS NOT NULL",
                url=other_url,
            )
        )
        # Safe preserved Role is reused, never widened.
        command.upgrade(Config(str(CONFIG)), "head")
        command.downgrade(Config(str(CONFIG)), PREVIOUS)
        os.environ["DATABASE_URL"] = other_url
        command.downgrade(Config(str(CONFIG)), PREVIOUS)
        assert (
            asyncio.run(
                scalar(
                    "SELECT count(*) FROM pg_roles WHERE rolname='aria_preview_runtime_owner'",
                    url=other_url,
                )
            )
            == 0
        )
    finally:
        os.environ["DATABASE_URL"] = TEST_DATABASE_URL
        if created:
            asyncio.run(database_command(f'DROP DATABASE "{database}"'))
        command.upgrade(Config(str(CONFIG)), "head")
        if original_env is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_env
