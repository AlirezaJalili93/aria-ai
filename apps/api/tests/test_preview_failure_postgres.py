"""Actual runtime authority for the bounded, owned-session permanent failure helper."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_artifact_foundation_postgres import API_ROOT, TEST_DATABASE_URL
from test_artifact_foundation_postgres import clean_artifact_schema as clean_artifact_schema
from test_preview_authority_postgres import allocated, claim, engine, finalize, release, states

pytestmark = pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Throwaway PostgreSQL required")


async def fail(connection, binding, code="PREVIEW_SOURCE_INVALID", *, job=None, event=None):
    await connection.execute(
        text("SELECT aria_internal.fail_preview(:job,:event,:code)"),
        {"job": job or binding.job, "event": event or binding.event, "code": code},
    )


async def job_failure(owner, binding):
    async with owner.connect() as connection:
        return (
            await connection.execute(
                text("SELECT status,error_code,error_detail,finished_at FROM jobs WHERE id=:id"),
                {"id": binding.job},
            )
        ).one()


@pytest.mark.parametrize(
    "code", ["PREVIEW_SOURCE_INVALID", "PREVIEW_SOURCE_UNSUPPORTED", "PREVIEW_DELIVERY_CONFLICT"]
)
def test_exact_owned_failure_and_same_reason_replay_preserve_domain_state(code):
    async def scenario():
        binding = await allocated()
        owner, worker = engine(), engine(worker=True)
        try:
            async with worker.connect() as connection:
                assert await connection.scalar(text("SELECT session_user")) == "aria_worker"
                await claim(connection, binding)
                await connection.commit()
                async with connection.begin():
                    await fail(connection, binding, code)
                first = await job_failure(owner, binding)
                assert tuple(first[:3]) == ("failed", code, None) and first[3] is not None
                async with connection.begin():
                    await fail(connection, binding, code)
                assert await job_failure(owner, binding) == first
                assert await states(owner, binding) == ("preparing", "publishing", "failed")
                async with owner.connect() as observer:
                    assert (
                        await observer.scalar(
                            text(
                                "SELECT count(*) FROM preview_publications "
                                "WHERE token_hash IS NOT NULL"
                            )
                        )
                        == 0
                    )
                    assert (
                        await observer.scalar(
                            text(
                                "SELECT count(*) FROM preview_representations "
                                "WHERE manifest_hash IS NOT NULL"
                            )
                        )
                        == 0
                    )
                with pytest.raises(DBAPIError) as denied:
                    async with connection.begin():
                        await finalize(connection, binding)
                assert getattr(denied.value.orig, "sqlstate", None) == "42501"
                assert await job_failure(owner, binding) == first
                async with connection.begin():
                    await release(connection, binding)
            async with worker.connect() as redelivery:
                with pytest.raises(DBAPIError) as denied:
                    async with redelivery.begin():
                        await claim(redelivery, binding)
                assert getattr(denied.value.orig, "sqlstate", None) == "42501"
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "code",
    [
        None,
        "",
        "timeout",
        "PREVIEW_STORAGE_ERROR",
        "PREVIEW_FINALIZATION_RECOVERABLE",
        "PREVIEW_PUBLICATION_REVOKED",
        "raw synthetic diagnostic",
    ],
)
def test_failure_reason_allowlist_rejects_transient_unknown_and_raw_data(code):
    async def scenario():
        binding = await allocated()
        owner, worker = engine(), engine(worker=True)
        try:
            async with worker.connect() as connection:
                await claim(connection, binding)
                await connection.commit()
                with pytest.raises(DBAPIError) as denied:
                    async with connection.begin():
                        await fail(connection, binding, code)
                assert getattr(denied.value.orig, "sqlstate", None) == "42501"
                assert await states(owner, binding) == ("preparing", "publishing", "running")
                async with connection.begin():
                    await release(connection, binding)
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "boundary",
    [
        "unclaimed",
        "foreign_session",
        "wrong_event",
        "wrong_job",
        "missing_live_lock",
        "revoked",
        "succeeded",
        "terminal_reason",
    ],
)
def test_failure_requires_exact_current_claim_live_lock_and_mutable_job(boundary):
    async def scenario():
        binding = await allocated()
        owner, worker = engine(), engine(worker=True)
        try:
            async with worker.connect() as connection, worker.connect() as foreign:
                if boundary != "unclaimed":
                    await claim(connection, binding)
                    await connection.commit()
                if boundary == "missing_live_lock":
                    await connection.execute(text("SELECT pg_advisory_unlock_all()"))
                    await connection.commit()
                elif boundary == "revoked":
                    async with owner.begin() as writer:
                        await writer.execute(
                            text(
                                "UPDATE preview_publications SET status='revoked',"
                                "revoked_at=CURRENT_TIMESTAMP WHERE id=:id"
                            ),
                            {"id": binding.publication},
                        )
                elif boundary == "succeeded":
                    async with connection.begin():
                        await finalize(connection, binding)
                elif boundary == "terminal_reason":
                    async with connection.begin():
                        await fail(connection, binding, "PREVIEW_SOURCE_UNSUPPORTED")
                before = await job_failure(owner, binding)
                candidate = foreign if boundary == "foreign_session" else connection
                with pytest.raises(DBAPIError) as denied:
                    async with candidate.begin():
                        await fail(
                            candidate,
                            binding,
                            event=uuid4() if boundary == "wrong_event" else None,
                            job=uuid4() if boundary == "wrong_job" else None,
                        )
                assert getattr(denied.value.orig, "sqlstate", None) == "42501"
                assert await job_failure(owner, binding) == before
                async with connection.begin():
                    await release(connection, binding)
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_failed_transition_rolls_back_atomically_and_can_commit_under_same_claim():
    async def scenario():
        binding = await allocated()
        owner, worker = engine(), engine(worker=True)
        try:
            async with worker.connect() as connection:
                await claim(connection, binding)
                await connection.commit()
                transaction = await connection.begin()
                await fail(connection, binding)
                await transaction.rollback()
                assert await states(owner, binding) == ("preparing", "publishing", "running")
                async with connection.begin():
                    await fail(connection, binding)
                assert await states(owner, binding) == ("preparing", "publishing", "failed")
                async with connection.begin():
                    await release(connection, binding)
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_cross_tenant_job_event_pair_cannot_fail_another_job():
    async def scenario():
        first, other = await allocated(), await allocated()
        owner, worker = engine(), engine(worker=True)
        try:
            async with worker.connect() as connection:
                await claim(connection, first)
                await connection.commit()
                with pytest.raises(DBAPIError) as denied:
                    async with connection.begin():
                        await fail(connection, other, event=first.event)
                assert getattr(denied.value.orig, "sqlstate", None) == "42501"
                assert (await job_failure(owner, other))[0] == "queued"
                assert (await job_failure(owner, first))[0] == "running"
                async with connection.begin():
                    await release(connection, first)
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_failure_helper_acl_owner_and_column_privilege_are_minimal():
    async def scenario():
        owner = engine()
        try:
            async with owner.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT p.prosecdef,p.proconfig,r.rolname FROM pg_proc p "
                            "JOIN pg_roles r ON r.oid=p.proowner WHERE "
                            "p.oid='aria_internal.fail_preview(uuid,uuid,text)'::regprocedure"
                        )
                    )
                ).one()
                assert tuple(row) == (True, ['search_path=""'], "aria_preview_runtime_owner")
                for role in ("anon", "authenticated"):
                    assert not await connection.scalar(
                        text(
                            "SELECT has_function_privilege(:role,"
                            "'aria_internal.fail_preview(uuid,uuid,text)','EXECUTE')"
                        ),
                        {"role": role},
                    )
                assert await connection.scalar(
                    text(
                        "SELECT has_function_privilege('aria_worker',"
                        "'aria_internal.fail_preview(uuid,uuid,text)','EXECUTE')"
                    )
                )
                assert not await connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a "
                        "WHERE p.oid='aria_internal.fail_preview(uuid,uuid,text)'::regprocedure "
                        "AND a.grantee=0 AND a.privilege_type='EXECUTE')"
                    )
                )
                assert await connection.scalar(
                    text(
                        "SELECT has_column_privilege('aria_preview_runtime_owner','public.jobs',"
                        "'error_code','SELECT')"
                    )
                )
                assert not await connection.scalar(
                    text(
                        "SELECT has_table_privilege('aria_preview_runtime_owner',"
                        "'public.jobs','SELECT')"
                    )
                )
                assert not await connection.scalar(
                    text(
                        "SELECT has_column_privilege('aria_preview_runtime_owner','public.jobs',"
                        "'error_detail','SELECT')"
                    )
                )
        finally:
            await owner.dispose()

    asyncio.run(scenario())


def test_failure_migration_downgrade_preserves_rows_and_four_original_helpers():
    binding = asyncio.run(allocated())
    owner = engine()

    async def check():
        try:
            async with owner.connect() as connection:
                assert (
                    await connection.scalar(text("SELECT count(*) FROM preview_publications")) == 1
                )
                assert await connection.scalar(
                    text(
                        "SELECT to_regprocedure('aria_internal.fail_preview(uuid,uuid,text)') "
                        "IS NULL"
                    )
                )
                assert await connection.scalar(
                    text(
                        "SELECT to_regprocedure('aria_internal.claim_preview(uuid,uuid)') "
                        "IS NOT NULL"
                    )
                )
                assert not await connection.scalar(
                    text(
                        "SELECT has_column_privilege('aria_preview_runtime_owner','public.jobs',"
                        "'error_code','SELECT')"
                    )
                )
        finally:
            await owner.dispose()

    config = Config(str(API_ROOT / "alembic.ini"))
    command.downgrade(config, "0040_preview_publication")
    asyncio.run(check())
    command.upgrade(config, "head")
    assert binding.publication is not None
