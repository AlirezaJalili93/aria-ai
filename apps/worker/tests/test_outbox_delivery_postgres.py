from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.outbox_delivery import OutboxDeliveryPersistenceError
from app.infrastructure.db.outbox_delivery import PostgresOutboxDeliveryRepository

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


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


async def _insert_event(
    engine: AsyncEngine,
    *,
    event_type: str = "context_added.v1",
    channel: str = "job_queue",
    available_at: datetime,
) -> UUID:
    event_id, job_id = uuid4(), uuid4()
    payload = {
        "jobId": str(job_id),
        "taskType": "context_source_parse",
        "payloadVersion": "1",
        "accountId": str(uuid4()),
        "projectId": str(uuid4()),
        "correlationId": str(uuid4()),
    }
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO public.outbox_events "
                "(id, aggregate_type, aggregate_id, event_type, delivery_channel, payload, "
                "available_at) VALUES (:id, 'context_source', :aggregate_id, :event_type, "
                ":channel, CAST(:payload AS jsonb), :available_at)"
            ),
            {
                "id": event_id,
                "aggregate_id": uuid4(),
                "event_type": event_type,
                "channel": channel,
                "payload": json.dumps(payload),
                "available_at": available_at,
            },
        )
    return event_id


async def _truncate(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE public.outbox_events"))


def test_concurrent_relays_never_claim_the_same_event_and_ignore_domain_events() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            await _truncate(engine)
            now = datetime.now(UTC)
            job_events = {
                await _insert_event(engine, available_at=now),
                await _insert_event(engine, event_type="unknown.v1", available_at=now),
            }
            await _insert_event(
                engine,
                event_type="requirement.conflict_detected",
                channel="domain_event",
                available_at=now,
            )
            first = PostgresOutboxDeliveryRepository(engine)
            second = PostgresOutboxDeliveryRepository(engine)
            batches = await asyncio.gather(
                first.claim_batch(now=now, lease_until=now + timedelta(seconds=30), limit=20),
                second.claim_batch(now=now, lease_until=now + timedelta(seconds=30), limit=20),
            )
            claimed = [event.id for batch in batches for event in batch]
            assert set(claimed) == job_events
            assert len(claimed) == len(set(claimed))
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_claim_is_committed_before_publish_and_expired_lease_is_reclaimed() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            await _truncate(engine)
            now = datetime.now(UTC)
            event_id = await _insert_event(engine, available_at=now)
            repository = PostgresOutboxDeliveryRepository(engine)
            first = await repository.claim_batch(
                now=now,
                lease_until=now + timedelta(seconds=30),
                limit=20,
            )
            assert len(first) == 1 and first[0].id == event_id
            async with engine.connect() as connection:
                visible = (
                    await connection.execute(
                        text(
                            "SELECT claim_id, attempt_count FROM public.outbox_events WHERE id=:id"
                        ),
                        {"id": event_id},
                    )
                ).one()
            assert visible.claim_id == first[0].claim_id and visible.attempt_count == 1
            assert await repository.claim_batch(
                now=now + timedelta(seconds=29),
                lease_until=now + timedelta(seconds=59),
                limit=20,
            ) == ()
            recovered = await repository.claim_batch(
                now=now + timedelta(seconds=31),
                lease_until=now + timedelta(seconds=61),
                limit=20,
            )
            assert len(recovered) == 1
            assert recovered[0].id == event_id
            assert recovered[0].reclaimed is True
            assert recovered[0].delivery_attempt == 2
            assert recovered[0].claim_id != first[0].claim_id
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_claim_token_guards_ack_retry_and_unknown_event_blocking() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            await _truncate(engine)
            now = datetime.now(UTC)
            await _insert_event(engine, event_type="unknown.v1", available_at=now)
            repository = PostgresOutboxDeliveryRepository(engine)
            claimed = (
                await repository.claim_batch(
                    now=now,
                    lease_until=now + timedelta(seconds=30),
                    limit=20,
                )
            )[0]
            with pytest.raises(OutboxDeliveryPersistenceError):
                await repository.mark_published(
                    event_id=claimed.id,
                    claim_id=uuid4(),
                    published_at=now,
                )
            await repository.block_unknown_event(
                event_id=claimed.id,
                claim_id=claimed.claim_id,
            )
            assert await repository.claim_batch(
                now=now + timedelta(minutes=5),
                lease_until=now + timedelta(minutes=6),
                limit=20,
            ) == ()
            async with engine.connect() as connection:
                status = await connection.scalar(
                    text("SELECT status FROM public.outbox_events WHERE id=:id"),
                    {"id": claimed.id},
                )
            assert status == "blocked_unknown_event"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_worker_outbox_privileges_are_column_limited_and_rls_scoped() -> None:
    async def scenario() -> None:
        engine = _engine()
        try:
            async with engine.connect() as connection:
                privileges = (
                    await connection.execute(
                        text(
                            "SELECT "
                            "has_table_privilege('aria_worker','public.outbox_events','SELECT') "
                            "AS can_select, "
                            "has_table_privilege('aria_worker','public.outbox_events','UPDATE') "
                            "AS can_update_all, "
                            "has_column_privilege('aria_worker','public.outbox_events',"
                            "'claim_id','UPDATE') AS can_update_claim, "
                            "has_column_privilege('aria_worker','public.outbox_events',"
                            "'payload','UPDATE') AS can_update_payload, "
                            "has_table_privilege('aria_worker','public.outbox_events','INSERT') "
                            "AS can_insert, "
                            "has_table_privilege('aria_worker','public.outbox_events','DELETE') "
                            "AS can_delete"
                        )
                    )
                ).one()
                policy = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
                        "AND tablename='outbox_events' "
                        "AND policyname='outbox_events_relay_worker_update'"
                    )
                )
            assert privileges == (True, False, True, False, False, False)
            assert policy == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
