from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4

from aria_observability import create_event_logger

from app.application.outbox_delivery import (
    OUTBOX_BATCH_SIZE,
    OUTBOX_LEASE_SECONDS,
    ClaimedOutboxEvent,
    DurableOutboxRelay,
    OutboxDeliveryPersistenceError,
    OutboxPublishError,
    UnknownOutboxEventError,
    outbox_backoff_seconds,
)


class _Repository:
    def __init__(self, events: tuple[ClaimedOutboxEvent, ...]) -> None:
        self.events = events
        self.claims: list[tuple[datetime, datetime, int]] = []
        self.published: list[tuple[UUID, UUID, datetime]] = []
        self.retries: list[tuple[UUID, UUID, datetime]] = []
        self.blocked: list[tuple[UUID, UUID]] = []
        self.fail_ack = False
        self.fail_claim = False

    async def claim_batch(
        self, *, now: datetime, lease_until: datetime, limit: int
    ) -> tuple[ClaimedOutboxEvent, ...]:
        if self.fail_claim:
            raise OutboxDeliveryPersistenceError
        self.claims.append((now, lease_until, limit))
        return self.events

    async def mark_published(
        self, *, event_id: UUID, claim_id: UUID, published_at: datetime
    ) -> None:
        if self.fail_ack:
            raise OutboxDeliveryPersistenceError
        self.published.append((event_id, claim_id, published_at))

    async def schedule_retry(
        self, *, event_id: UUID, claim_id: UUID, next_attempt_at: datetime
    ) -> None:
        self.retries.append((event_id, claim_id, next_attempt_at))

    async def block_unknown_event(self, *, event_id: UUID, claim_id: UUID) -> None:
        self.blocked.append((event_id, claim_id))


class _Publisher:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.events: list[UUID] = []

    async def publish(self, event: ClaimedOutboxEvent) -> None:
        self.events.append(event.id)
        if self.failure is not None:
            raise self.failure


def _event(*, attempt: int = 1, reclaimed: bool = False) -> ClaimedOutboxEvent:
    now = datetime(2026, 9, 21, 8, tzinfo=UTC)
    return ClaimedOutboxEvent(
        id=uuid4(),
        account_id=uuid4(),
        aggregate_type="context_source",
        aggregate_id=uuid4(),
        event_type="context_added.v1",
        delivery_channel="job_queue",
        payload={"customer_content": "must-not-log"},
        delivery_attempt=attempt,
        claim_id=uuid4(),
        claimed_at=now,
        lease_until=now + timedelta(seconds=30),
        created_at=now - timedelta(seconds=4),
        reclaimed=reclaimed,
    )


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_success_claims_with_frozen_batch_and_lease_then_acknowledges() -> None:
    now = datetime(2026, 9, 21, 9, tzinfo=UTC)
    event = _event(reclaimed=True)
    repository = _Repository((event,))
    publisher = _Publisher()
    stream = StringIO()
    relay = DurableOutboxRelay(
        repository=repository,
        publisher=publisher,
        event_logger=_logger(stream),
        clock=lambda: now,
    )

    result = asyncio.run(relay.run_once())

    assert repository.claims == [
        (now, now + timedelta(seconds=OUTBOX_LEASE_SECONDS), OUTBOX_BATCH_SIZE)
    ]
    assert publisher.events == [event.id]
    assert repository.published == [(event.id, event.claim_id, now)]
    assert result.published == 1 and result.reclaimed == 1
    names = [json.loads(line)["event_name"] for line in stream.getvalue().splitlines()]
    assert names == ["outbox.claimed", "outbox.lease_expired_reclaimed", "outbox.published"]
    assert "must-not-log" not in stream.getvalue()


def test_publish_failure_uses_deterministic_backoff_without_terminal_state() -> None:
    now = datetime(2026, 9, 21, 9, tzinfo=UTC)
    event = _event(attempt=4)
    repository = _Repository((event,))
    relay = DurableOutboxRelay(
        repository=repository,
        publisher=_Publisher(OutboxPublishError()),
        event_logger=_logger(StringIO()),
        clock=lambda: now,
    )

    result = asyncio.run(relay.run_once())

    assert repository.retries == [(event.id, event.claim_id, now + timedelta(seconds=16))]
    assert result.failed == 1 and result.published == 0


def test_unknown_event_is_blocked_and_removed_from_automatic_eligibility() -> None:
    event = replace(_event(), event_type="unapproved.v1")
    repository = _Repository((event,))
    relay = DurableOutboxRelay(
        repository=repository,
        publisher=_Publisher(UnknownOutboxEventError()),
        event_logger=_logger(StringIO()),
    )

    result = asyncio.run(relay.run_once())

    assert repository.blocked == [(event.id, event.claim_id)]
    assert result.blocked == 1 and result.published == 0


def test_publish_success_with_ack_failure_leaves_claim_for_lease_recovery() -> None:
    event = _event()
    repository = _Repository((event,))
    repository.fail_ack = True
    publisher = _Publisher()
    stream = StringIO()
    relay = DurableOutboxRelay(
        repository=repository,
        publisher=publisher,
        event_logger=_logger(stream),
    )

    result = asyncio.run(relay.run_once())

    assert publisher.events == [event.id]
    assert repository.published == []
    assert result.published == 0
    assert "outbox.acknowledgement_failed" in stream.getvalue()


def test_claim_outage_is_recoverable_and_safely_logged() -> None:
    repository = _Repository(())
    repository.fail_claim = True
    stream = StringIO()
    relay = DurableOutboxRelay(
        repository=repository,
        publisher=_Publisher(),
        event_logger=_logger(stream),
    )

    try:
        asyncio.run(relay.run_once())
    except OutboxDeliveryPersistenceError:
        pass
    else:
        raise AssertionError("Claim failure must remain observable to the runner")
    assert "OUTBOX_CLAIM_FAILED" in stream.getvalue()


def test_backoff_is_bounded_and_rejects_invalid_attempts() -> None:
    assert [outbox_backoff_seconds(value) for value in range(1, 8)] == [
        2,
        4,
        8,
        16,
        32,
        60,
        60,
    ]
    assert outbox_backoff_seconds(2_000_000_000) == 60
    for value in (0, -1, True):
        try:
            outbox_backoff_seconds(value)
        except ValueError:
            continue
        raise AssertionError("Invalid attempt must be rejected")
