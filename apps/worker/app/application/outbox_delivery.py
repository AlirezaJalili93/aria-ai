from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from aria_observability import StructuredEventLogger

OUTBOX_POLL_INTERVAL_SECONDS = 2
OUTBOX_BATCH_SIZE = 20
OUTBOX_LEASE_SECONDS = 30
OUTBOX_BACKOFF_BASE_SECONDS = 2
OUTBOX_BACKOFF_CAP_SECONDS = 60

DeliveryChannel = Literal["job_queue", "domain_event"]


class OutboxDeliveryError(Exception):
    """Base class for bounded Outbox delivery failures."""


class OutboxDeliveryPersistenceError(OutboxDeliveryError):
    """The PostgreSQL claim or acknowledgement operation failed."""


class OutboxPublishError(OutboxDeliveryError):
    """The Queue transport rejected or could not accept the delivery."""


class UnknownOutboxEventError(OutboxDeliveryError):
    """A job_queue event has no approved task mapping."""


@dataclass(frozen=True, slots=True)
class ClaimedOutboxEvent:
    id: UUID
    account_id: UUID | None
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    delivery_channel: DeliveryChannel
    payload: dict[str, object]
    delivery_attempt: int
    claim_id: UUID
    claimed_at: datetime
    lease_until: datetime
    created_at: datetime
    reclaimed: bool


class OutboxDeliveryRepository(Protocol):
    async def claim_batch(
        self, *, now: datetime, lease_until: datetime, limit: int
    ) -> tuple[ClaimedOutboxEvent, ...]: ...

    async def mark_published(
        self, *, event_id: UUID, claim_id: UUID, published_at: datetime
    ) -> None: ...

    async def schedule_retry(
        self, *, event_id: UUID, claim_id: UUID, next_attempt_at: datetime
    ) -> None: ...

    async def block_unknown_event(self, *, event_id: UUID, claim_id: UUID) -> None: ...


class OutboxQueuePublisher(Protocol):
    async def publish(self, event: ClaimedOutboxEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class RelayCycleResult:
    claimed: int
    published: int
    failed: int
    blocked: int
    reclaimed: int


class DurableOutboxRelay:
    def __init__(
        self,
        *,
        repository: OutboxDeliveryRepository,
        publisher: OutboxQueuePublisher,
        event_logger: StructuredEventLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._event_logger = event_logger
        self._clock = clock

    async def run_once(self) -> RelayCycleResult:
        claimed_at = self._clock()
        try:
            events = await self._repository.claim_batch(
                now=claimed_at,
                lease_until=claimed_at + timedelta(seconds=OUTBOX_LEASE_SECONDS),
                limit=OUTBOX_BATCH_SIZE,
            )
        except OutboxDeliveryPersistenceError:
            self._event_logger.emit(
                "outbox.claim_failed",
                level="ERROR",
                status="recoverable",
                error_code="OUTBOX_CLAIM_FAILED",
            )
            raise
        published = failed = blocked = reclaimed = 0
        for event in events:
            reclaimed += int(event.reclaimed)
            self._emit("outbox.claimed", event, status="claimed")
            if event.reclaimed:
                self._emit("outbox.lease_expired_reclaimed", event, status="reclaimed")
            try:
                await self._publisher.publish(event)
            except UnknownOutboxEventError:
                blocked += int(await self._block_unknown(event))
                continue
            except OutboxPublishError:
                await self._schedule_retry(event)
                failed += 1
                continue

            try:
                published_at = self._clock()
                await self._repository.mark_published(
                    event_id=event.id,
                    claim_id=event.claim_id,
                    published_at=published_at,
                )
            except OutboxDeliveryPersistenceError:
                self._emit(
                    "outbox.acknowledgement_failed",
                    event,
                    level="ERROR",
                    status="pending",
                    error_code="OUTBOX_ACKNOWLEDGEMENT_FAILED",
                )
                continue
            published += 1
            self._emit("outbox.published", event, status="published")

        return RelayCycleResult(
            claimed=len(events),
            published=published,
            failed=failed,
            blocked=blocked,
            reclaimed=reclaimed,
        )

    async def _schedule_retry(self, event: ClaimedOutboxEvent) -> None:
        next_attempt_at = self._clock() + timedelta(
            seconds=outbox_backoff_seconds(event.delivery_attempt)
        )
        try:
            await self._repository.schedule_retry(
                event_id=event.id,
                claim_id=event.claim_id,
                next_attempt_at=next_attempt_at,
            )
        except OutboxDeliveryPersistenceError:
            self._emit(
                "outbox.retry_schedule_failed",
                event,
                level="ERROR",
                status="pending",
                error_code="OUTBOX_RETRY_SCHEDULE_FAILED",
            )
            return
        self._emit(
            "outbox.publish_failed",
            event,
            level="ERROR",
            status="pending",
            error_code="OUTBOX_PUBLISH_FAILED",
        )

    async def _block_unknown(self, event: ClaimedOutboxEvent) -> bool:
        try:
            await self._repository.block_unknown_event(
                event_id=event.id,
                claim_id=event.claim_id,
            )
        except OutboxDeliveryPersistenceError:
            self._emit(
                "outbox.block_unknown_failed",
                event,
                level="ERROR",
                status="pending",
                error_code="OUTBOX_BLOCK_UNKNOWN_FAILED",
            )
            return False
        self._emit(
            "outbox.blocked_unknown_event",
            event,
            level="ERROR",
            status="blocked_unknown_event",
            error_code="OUTBOX_UNKNOWN_EVENT",
        )
        return True

    def _emit(
        self,
        event_name: str,
        event: ClaimedOutboxEvent,
        *,
        status: str,
        level: str = "INFO",
        error_code: str | None = None,
    ) -> None:
        now = self._clock()
        fields: dict[str, object] = {
            "outbox_event_id": str(event.id),
            "aggregate_type": event.aggregate_type,
            "aggregate_id": str(event.aggregate_id),
            "task_type": event.event_type,
            "attempt": event.delivery_attempt,
            "latency_ms": max(0.0, (now - event.created_at).total_seconds() * 1000),
            "status": status,
        }
        if error_code is not None:
            fields["error_code"] = error_code
        self._event_logger.emit(event_name, level=level, **fields)


class OutboxRelayRunner:
    def __init__(
        self,
        relay: DurableOutboxRelay,
        *,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._relay = relay
        self._sleeper = sleeper

    async def run_forever(self) -> None:
        while True:
            with suppress(OutboxDeliveryPersistenceError):
                await self._relay.run_once()
            await self._sleeper(OUTBOX_POLL_INTERVAL_SECONDS)


def outbox_backoff_seconds(delivery_attempt: int) -> int:
    if isinstance(delivery_attempt, bool) or delivery_attempt < 1:
        raise ValueError("delivery_attempt must be at least one")
    if delivery_attempt >= 6:
        return OUTBOX_BACKOFF_CAP_SECONDS
    return min(
        OUTBOX_BACKOFF_CAP_SECONDS,
        OUTBOX_BACKOFF_BASE_SECONDS * (2 ** (delivery_attempt - 1)),
    )
