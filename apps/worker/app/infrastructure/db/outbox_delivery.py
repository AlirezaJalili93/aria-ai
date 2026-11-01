from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.outbox_delivery import (
    ClaimedOutboxEvent,
    DeliveryChannel,
    OutboxDeliveryPersistenceError,
)


class PostgresOutboxDeliveryRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def claim_batch(
        self, *, now: datetime, lease_until: datetime, limit: int
    ) -> tuple[ClaimedOutboxEvent, ...]:
        try:
            async with self._engine.begin() as connection:
                rows = (
                    await connection.execute(
                        text(
                            """
                            WITH eligible AS (
                                SELECT id, (lease_until IS NOT NULL) AS reclaimed
                                FROM public.outbox_events
                                WHERE delivery_channel = 'job_queue'
                                  AND status = 'pending'
                                  AND available_at <= :now
                                  AND (lease_until IS NULL OR lease_until <= :now)
                                ORDER BY available_at ASC, created_at ASC, id ASC
                                FOR UPDATE SKIP LOCKED
                                LIMIT :limit
                            )
                            UPDATE public.outbox_events AS event
                            SET claim_id = gen_random_uuid(),
                                claimed_at = :now,
                                lease_until = :lease_until,
                                attempt_count = event.attempt_count + 1
                            FROM eligible
                            WHERE event.id = eligible.id
                            RETURNING event.id, event.account_id, event.aggregate_type,
                                      event.aggregate_id, event.event_type,
                                      event.delivery_channel, event.payload,
                                      event.attempt_count, event.claim_id, event.claimed_at,
                                      event.lease_until, event.created_at, eligible.reclaimed
                            """
                        ),
                        {"now": now, "lease_until": lease_until, "limit": limit},
                    )
                ).mappings().all()
        except SQLAlchemyError:
            raise OutboxDeliveryPersistenceError from None
        return tuple(_claimed_event(row) for row in rows)

    async def mark_published(
        self, *, event_id: UUID, claim_id: UUID, published_at: datetime
    ) -> None:
        await self._finish_claim(
            event_id=event_id,
            claim_id=claim_id,
            assignments="status='published', published_at=:value",
            parameters={"value": published_at},
        )

    async def schedule_retry(
        self, *, event_id: UUID, claim_id: UUID, next_attempt_at: datetime
    ) -> None:
        await self._finish_claim(
            event_id=event_id,
            claim_id=claim_id,
            assignments="status='pending', available_at=:value",
            parameters={"value": next_attempt_at},
        )

    async def block_unknown_event(self, *, event_id: UUID, claim_id: UUID) -> None:
        await self._finish_claim(
            event_id=event_id,
            claim_id=claim_id,
            assignments="status='blocked_unknown_event'",
            parameters={},
        )

    async def _finish_claim(
        self,
        *,
        event_id: UUID,
        claim_id: UUID,
        assignments: str,
        parameters: dict[str, object],
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                result = await connection.execute(
                    text(
                        f"UPDATE public.outbox_events SET {assignments}, "
                        "claim_id=NULL, claimed_at=NULL, lease_until=NULL "
                        "WHERE id=:event_id AND claim_id=:claim_id AND status='pending'"
                    ),
                    {"event_id": event_id, "claim_id": claim_id, **parameters},
                )
                if result.rowcount != 1:
                    raise OutboxDeliveryPersistenceError
        except OutboxDeliveryPersistenceError:
            raise
        except SQLAlchemyError:
            raise OutboxDeliveryPersistenceError from None


def _claimed_event(row: RowMapping) -> ClaimedOutboxEvent:
    values = row
    return ClaimedOutboxEvent(
        id=cast(UUID, values["id"]),
        account_id=cast(UUID | None, values["account_id"]),
        aggregate_type=cast(str, values["aggregate_type"]),
        aggregate_id=cast(UUID, values["aggregate_id"]),
        event_type=cast(str, values["event_type"]),
        delivery_channel=cast(DeliveryChannel, values["delivery_channel"]),
        payload=cast(dict[str, object], values["payload"]),
        delivery_attempt=cast(int, values["attempt_count"]),
        claim_id=cast(UUID, values["claim_id"]),
        claimed_at=cast(datetime, values["claimed_at"]),
        lease_until=cast(datetime, values["lease_until"]),
        created_at=cast(datetime, values["created_at"]),
        reclaimed=cast(bool, values["reclaimed"]),
    )
