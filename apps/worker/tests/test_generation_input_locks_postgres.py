"""Least-privilege, tenant-bound lock contract for AI-02 and AI-03."""

from __future__ import annotations

import asyncio
import json
import os
import re
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None
    or not re.fullmatch(
        r"aria_0077_test(?:_[a-z0-9_]+)?",
        TEST_DATABASE_URL.split("/")[-1].split("?")[0],
    ),
    reason="Dedicated aria_0077_test PostgreSQL database is required",
)


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def test_generation_lock_helpers_are_scoped_and_worker_is_not_elevated() -> None:
    async def scenario() -> None:
        owner_engine = create_async_engine(_database_url(), poolclass=NullPool)
        worker_engine = create_async_engine(
            _database_url(),
            poolclass=NullPool,
            connect_args={"server_settings": {"role": "aria_worker"}},
        )
        actor_id = uuid4()
        account_a, account_b = uuid4(), uuid4()
        project_a, project_b = uuid4(), uuid4()
        context_a, context_b = uuid4(), uuid4()
        requirement_a, requirement_b = uuid4(), uuid4()
        requirement_job, gap_job = uuid4(), uuid4()
        try:
            async with owner_engine.begin() as connection:
                await connection.execute(text("TRUNCATE public.accounts CASCADE"))
                await connection.execute(
                    text("INSERT INTO public.profiles (user_id) VALUES (:id)"),
                    {"id": actor_id},
                )
                for account_id, project_id, context_id, requirement_id in (
                    (account_a, project_a, context_a, requirement_a),
                    (account_b, project_b, context_b, requirement_b),
                ):
                    await connection.execute(
                        text("INSERT INTO public.accounts (id) VALUES (:id)"),
                        {"id": account_id},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO public.projects "
                            "(id, account_id, owner_id, title, project_type, "
                            "current_context_version) VALUES "
                            "(:project_id, :account_id, :actor_id, 'Synthetic', 'landing', 1)"
                        ),
                        {"project_id": project_id, "account_id": account_id, "actor_id": actor_id},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO public.context_items "
                            "(id, account_id, project_id, context_version, item_type, "
                            "content, source_refs, status, created_by_type) VALUES "
                            "(:id, :account_id, :project_id, 1, 'unknown', "
                            "'synthetic fixture', '[]'::jsonb, 'proposed', 'ai')"
                        ),
                        {"id": context_id, "account_id": account_id, "project_id": project_id},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO public.requirements "
                            "(id, account_id, project_id, context_version, category, "
                            "title, description, priority, status, created_by_type) VALUES "
                            "(:id, :account_id, :project_id, 1, 'functional', "
                            "'Synthetic', 'Synthetic', 'must', 'draft', 'ai')"
                        ),
                        {"id": requirement_id, "account_id": account_id, "project_id": project_id},
                    )
                for job_id, job_type in (
                    (requirement_job, "requirement_generation"),
                    (gap_job, "gap_detection"),
                ):
                    await connection.execute(
                        text(
                            "INSERT INTO public.jobs "
                            "(id, account_id, project_id, job_type, status, payload_ref, "
                            "attempt_count, max_attempts, correlation_id, available_at) "
                            "VALUES (:id, :account_id, :project_id, :job_type, 'running', "
                            "CAST(:payload_ref AS jsonb), 1, 1, :correlation_id, CURRENT_TIMESTAMP)"
                        ),
                        {
                            "id": job_id,
                            "account_id": account_a,
                            "project_id": project_a,
                            "job_type": job_type,
                            "payload_ref": json.dumps({"context_version": 1}),
                            "correlation_id": uuid4(),
                        },
                    )

            async with owner_engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT rolcanlogin, rolbypassrls FROM pg_catalog.pg_roles "
                            "WHERE rolname='aria_generation_lock_owner'"
                        )
                    )
                ).one()
                assert row == (False, False)
                for function_name in (
                    "lock_requirement_generation_inputs",
                    "lock_gap_detection_inputs",
                ):
                    function_acl = (
                        await connection.execute(
                            text(
                                "SELECT p.prosecdef, p.proconfig, "
                                "pg_catalog.pg_get_userbyid(p.proowner), "
                                "has_function_privilege('aria_worker', p.oid, 'EXECUTE'), "
                                "EXISTS (SELECT 1 FROM pg_catalog.aclexplode(p.proacl) a "
                                "WHERE a.grantee NOT IN (p.proowner, "
                                "(SELECT oid FROM pg_catalog.pg_roles "
                                "WHERE rolname='aria_worker')) "
                                "AND a.privilege_type='EXECUTE') "
                                "FROM pg_catalog.pg_proc p "
                                "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
                                "WHERE n.nspname='aria_internal' AND p.proname=:name"
                            ),
                            {"name": function_name},
                        )
                    ).one()
                    assert function_acl[0] is True
                    assert len(function_acl[1]) == 1
                    assert function_acl[1][0].startswith("search_path=")
                    assert function_acl[1][0].split("=", 1)[1].strip('"') == ""
                    assert function_acl[2] == "aria_generation_lock_owner"
                    assert function_acl[3] is True
                    assert function_acl[4] is False
                for relation in ("context_items", "requirements"):
                    permissions = (
                        await connection.execute(
                            text(
                                "SELECT has_table_privilege('aria_worker', :relation, 'UPDATE'), "
                                "has_table_privilege('aria_worker', :relation, 'DELETE'), "
                                "has_column_privilege('aria_worker', :relation, 'id', 'UPDATE')"
                            ),
                            {"relation": f"public.{relation}"},
                        )
                    ).one()
                    assert permissions == (False, False, False)

            for function_name in (
                "lock_requirement_generation_inputs",
                "lock_gap_detection_inputs",
            ):
                async with worker_engine.begin() as connection:
                    await connection.execute(
                        text(
                            f"SELECT aria_internal.{function_name}("
                            ":job_id, :account_id, :project_id, 1)"
                        ),
                        {
                            "job_id": requirement_job
                            if function_name == "lock_requirement_generation_inputs"
                            else gap_job,
                            "account_id": account_a,
                            "project_id": project_a,
                        },
                    )

                async with worker_engine.connect() as connection:
                    with pytest.raises(DBAPIError):
                        await connection.execute(
                            text(
                                f"SELECT aria_internal.{function_name}("
                                ":job_id, :account_id, :project_id, 1)"
                            ),
                            {
                                "job_id": requirement_job
                                if function_name == "lock_requirement_generation_inputs"
                                else gap_job,
                                "account_id": account_b,
                                "project_id": project_b,
                            },
                        )

            for relation, row_id in (
                ("context_items", context_a),
                ("requirements", requirement_a),
            ):
                async with worker_engine.connect() as connection:
                    with pytest.raises(DBAPIError):
                        await connection.execute(
                            text(f"UPDATE public.{relation} SET id=id WHERE id=:id"),
                            {"id": row_id},
                        )
                async with worker_engine.connect() as connection:
                    with pytest.raises(DBAPIError):
                        await connection.execute(
                            text(f"DELETE FROM public.{relation} WHERE id=:id"),
                            {"id": row_id},
                        )

            async with worker_engine.begin() as worker_connection:
                await worker_connection.execute(
                    text(
                        "SELECT aria_internal.lock_gap_detection_inputs("
                        ":job_id, :account_id, :project_id, 1)"
                    ),
                    {"job_id": gap_job, "account_id": account_a, "project_id": project_a},
                )
                for relation, row_id in (
                    ("context_items", context_b),
                    ("requirements", requirement_b),
                ):
                    async with owner_engine.begin() as connection:
                        await connection.execute(
                            text(f"UPDATE public.{relation} SET status=status WHERE id=:id"),
                            {"id": row_id},
                        )
                for relation, row_id in (
                    ("context_items", context_a),
                    ("requirements", requirement_a),
                ):
                    with pytest.raises(DBAPIError):
                        async with owner_engine.begin() as connection:
                            await connection.execute(text("SET LOCAL lock_timeout = '100ms'"))
                            await connection.execute(
                                text(
                                    f"UPDATE public.{relation} SET status=status WHERE id=:id"
                                ),
                                {"id": row_id},
                            )
            async with owner_engine.begin() as connection:
                await connection.execute(
                    text("UPDATE public.context_items SET status=status WHERE id=:id"),
                    {"id": context_a},
                )

            async with owner_engine.begin() as connection:
                await connection.execute(text("SET LOCAL ROLE aria_generation_lock_owner"))
                context_count = await connection.scalar(
                    text("SELECT count(*) FROM public.context_items")
                )
                requirement_count = await connection.scalar(
                    text("SELECT count(*) FROM public.requirements")
                )
                assert context_count == 0
                assert requirement_count == 0
        finally:
            await worker_engine.dispose()
            await owner_engine.dispose()

    asyncio.run(scenario())
