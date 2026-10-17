from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import create_event_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.context_parser import CanonicalTextParser
from app.application.txt_parser_consumer import ParserJobMessage, TxtParserConsumer
from app.infrastructure.db.txt_parser_runtime import (
    PostgresJobExecutionGuard,
    SqlAlchemyTxtParserJobStore,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


@dataclass
class _Fixture:
    user_id: UUID
    account_id: UUID
    project_id: UUID
    source_id: UUID
    source_version_id: UUID
    job_id: UUID
    outbox_event_id: UUID
    correlation_id: UUID


class _UnusedReader:
    async def read_private(self, *, storage_reference: str) -> bytes:
        raise AssertionError(storage_reference)


class _Metrics:
    queue_wait_count = 0

    def observe_queue_wait(self, duration_ms: float, *, parser_type: str) -> None:
        assert duration_ms >= 0 and parser_type == "text"
        self.queue_wait_count += 1

    def observe_parse_latency(
        self, duration_ms: float, *, parser_type: str, outcome: str
    ) -> None:
        assert duration_ms >= 0 and parser_type == "text" and outcome in {"success", "failure"}

    def record_parse_outcome(
        self, *, parser_type: str, outcome: str, failure_class: str | None = None
    ) -> None:
        del failure_class
        assert parser_type == "text" and outcome in {"success", "failure"}


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    if TEST_DATABASE_URL.startswith("postgresql+asyncpg://"):
        value = TEST_DATABASE_URL
    elif TEST_DATABASE_URL.startswith("postgres://"):
        value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        value = TEST_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def _engine() -> AsyncEngine:
    return create_async_engine(_database_url(), poolclass=NullPool)


async def _seed(engine: AsyncEngine) -> _Fixture:
    fixture = _Fixture(*(uuid4() for _ in range(8)))
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE public.accounts CASCADE"))
        await connection.execute(
            text("INSERT INTO profiles (user_id) VALUES (:user_id)"),
            {"user_id": fixture.user_id},
        )
        await connection.execute(
            text("INSERT INTO accounts (id) VALUES (:account_id)"),
            {"account_id": fixture.account_id},
        )
        await connection.execute(
            text(
                "INSERT INTO account_memberships "
                "(id, account_id, user_id, role, status) "
                "VALUES (:id, :account_id, :user_id, 'owner', 'active')"
            ),
            {
                "id": uuid4(),
                "account_id": fixture.account_id,
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
                "VALUES (:project_id, :account_id, :user_id, 'Test', 'landing')"
            ),
            {
                "project_id": fixture.project_id,
                "account_id": fixture.account_id,
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO context_sources "
                "(id, account_id, project_id, source_type, status, raw_text, created_by) "
                "VALUES (:source_id, :account_id, :project_id, 'text', 'uploaded', "
                ":raw_text, :user_id)"
            ),
            {
                "source_id": fixture.source_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "raw_text": "متن   فارسی\r\nنسخه",
                "user_id": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO context_source_versions "
                "(id, account_id, project_id, source_id, version_no, parse_status) "
                "VALUES (:version_id, :account_id, :project_id, :source_id, 1, 'pending')"
            ),
            {
                "version_id": fixture.source_version_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "source_id": fixture.source_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO jobs "
                "(id, account_id, project_id, job_type, payload_ref, max_attempts, correlation_id) "
                "VALUES (:job_id, :account_id, :project_id, 'context_source_parse', "
                "CAST(:payload AS jsonb), 1, :correlation_id)"
            ),
            {
                "job_id": fixture.job_id,
                "account_id": fixture.account_id,
                "project_id": fixture.project_id,
                "payload": json.dumps(
                    {
                        "source_id": str(fixture.source_id),
                        "source_version_id": str(fixture.source_version_id),
                    }
                ),
                "correlation_id": fixture.correlation_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, account_id, aggregate_type, aggregate_id, event_type, "
                "delivery_channel, payload) "
                "VALUES (:event_id, :account_id, 'context_source', :source_id, "
                "'context_added.v1', 'job_queue', CAST(:payload AS jsonb))"
            ),
            {
                "event_id": fixture.outbox_event_id,
                "account_id": fixture.account_id,
                "source_id": fixture.source_id,
                "payload": json.dumps({"jobId": str(fixture.job_id)}),
            },
        )
    return fixture


def test_advisory_guard_is_atomic_and_releases_for_recovery() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            first = PostgresJobExecutionGuard(engine)
            second = PostgresJobExecutionGuard(engine)
            assert await first.acquire(fixture.job_id) == "acquired"
            assert await second.acquire(fixture.job_id) == "already_in_progress"
            await first.release(fixture.job_id)
            assert await second.acquire(fixture.job_id) == "acquired"
            await second.release(fixture.job_id)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_processing_recovery_and_atomic_success_reuse_the_same_rows() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            fixture = await _seed(engine)
            message = ParserJobMessage("1", fixture.outbox_event_id, fixture.job_id)
            first_guard = PostgresJobExecutionGuard(engine)
            store = SqlAlchemyTxtParserJobStore(engine)
            assert await first_guard.acquire(fixture.job_id) == "acquired"
            first = await store.prepare(message)
            assert first.first_attempt is True
            await first_guard.release(fixture.job_id)

            recovery_guard = PostgresJobExecutionGuard(engine)
            assert await recovery_guard.acquire(fixture.job_id) == "acquired"
            recovered = await store.prepare(message)
            assert recovered.first_attempt is False
            assert recovered.source_id == fixture.source_id
            assert recovered.source_version_id == fixture.source_version_id

            stream = StringIO()
            metrics = _Metrics()
            consumer = TxtParserConsumer(
                guard=recovery_guard,
                store=store,
                parser=CanonicalTextParser(
                    metrics=metrics,  # type: ignore[arg-type]
                    event_logger=create_event_logger(
                        service="aria-worker",
                        environment="test",
                        app_version="0.1.0",
                        release_commit_sha=None,
                        level="INFO",
                        stream=stream,
                    ),
                ),
                object_reader=_UnusedReader(),
                metrics=metrics,  # type: ignore[arg-type]
                event_logger=create_event_logger(
                    service="aria-worker",
                    environment="test",
                    app_version="0.1.0",
                    release_commit_sha=None,
                    level="INFO",
                    stream=stream,
                ),
                clock=lambda: datetime.now(UTC),
            )
            # Release the recovery probe lock before the normal consumer entry.
            await recovery_guard.release(fixture.job_id)
            assert (await consumer.execute(message)).status == "succeeded"
            assert (await consumer.execute(message)).status == "already_completed"
            assert metrics.queue_wait_count == 0

            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            """
                            SELECT j.status AS job_status,
                                   j.attempt_count,
                                   s.status AS source_status,
                                   v.parse_status,
                                   v.canonical_text,
                                   v.content_hash
                            FROM jobs j
                            JOIN context_sources s ON s.id=:source_id
                            JOIN context_source_versions v ON v.id=:version_id
                            WHERE j.id=:job_id
                            """
                        ),
                        {
                            "job_id": fixture.job_id,
                            "source_id": fixture.source_id,
                            "version_id": fixture.source_version_id,
                        },
                    )
                ).mappings().one()
            assert row["job_status"] == "succeeded"
            assert row["attempt_count"] == 1
            assert row["source_status"] == "ready"
            assert row["parse_status"] == "ready"
            assert row["canonical_text"] == "متن فارسی\nنسخه"
            assert re.fullmatch(r"[0-9a-f]{64}", row["content_hash"])
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_role_has_only_parser_and_relay_table_commands() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            async with engine.connect() as connection:
                checks = (
                    await connection.execute(
                        text(
                            """
                            SELECT
                              has_table_privilege(
                                'aria_worker','public.jobs','SELECT'
                              ) AS jobs_select,
                              has_table_privilege(
                                'aria_worker','public.jobs','UPDATE'
                              ) AS jobs_update,
                              has_table_privilege(
                                'aria_worker','public.jobs','INSERT'
                              ) AS jobs_insert,
                              has_table_privilege(
                                'aria_worker','public.jobs','DELETE'
                              ) AS jobs_delete,
                              has_table_privilege(
                                'aria_worker','public.outbox_events','SELECT'
                              ) AS outbox_select,
                              has_column_privilege(
                                'aria_worker','public.outbox_events','claim_id','UPDATE'
                              ) AS outbox_claim_update,
                              has_column_privilege(
                                'aria_worker','public.outbox_events','payload','UPDATE'
                              ) AS outbox_payload_update
                            """
                        )
                    )
                ).mappings().one()
                policies = {
                    row[0]
                    for row in (
                        await connection.execute(
                            text(
                                "SELECT policyname FROM pg_policies "
                                "WHERE roles @> ARRAY['aria_worker']::name[]"
                            )
                        )
                    ).all()
                }
            assert dict(checks) == {
                "jobs_select": True,
                "jobs_update": True,
                "jobs_insert": False,
                "jobs_delete": False,
                "outbox_select": True,
                "outbox_claim_update": True,
                "outbox_payload_update": False,
            }
            assert {
                "jobs_parser_worker_select",
                "jobs_parser_worker_update",
                "context_sources_parser_worker_select",
                "context_sources_parser_worker_update",
                "context_source_versions_parser_worker_select",
                "context_source_versions_parser_worker_update",
                "outbox_events_parser_worker_select",
                "outbox_events_relay_worker_update",
            }.issubset(policies)
        finally:
            await engine.dispose()

    asyncio.run(scenario())
