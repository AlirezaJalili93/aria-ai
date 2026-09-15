from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.jobs.application.outbox_relay import OutboxRelay
from app.modules.jobs.application.ports import JobsRepositoryError, JobsUnitOfWork
from app.modules.jobs.domain.job import OutboxEvent


class FakePublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[OutboxEvent] = []
        self.fail = fail

    async def publish(self, event: OutboxEvent) -> None:
        self.events.append(event)
        if self.fail:
            raise RuntimeError("transport unavailable")


class FakeOutbox:
    def __init__(self, event: OutboxEvent, *, fail_mark: bool = False) -> None:
        self.event = event
        self.fail_mark = fail_mark

    async def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        if self.fail_mark:
            raise JobsRepositoryError
        assert event_id == self.event.id
        self.event = OutboxEvent(
            id=self.event.id,
            account_id=self.event.account_id,
            aggregate_type=self.event.aggregate_type,
            aggregate_id=self.event.aggregate_id,
            event_type=self.event.event_type,
            payload=self.event.payload,
            status="published",
            attempt_count=self.event.attempt_count,
            available_at=self.event.available_at,
            created_at=self.event.created_at,
            published_at=published_at,
        )


class FakeUnitOfWork(JobsUnitOfWork):
    def __init__(self, outbox: FakeOutbox) -> None:
        self._outbox = outbox
        self.commits = 0

    @property
    def jobs(self):
        raise AssertionError("The relay must not touch Jobs state")

    @property
    def outbox(self) -> FakeOutbox:
        return self._outbox

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.commits += 1


def _event(*, attempt_count: int = 0) -> OutboxEvent:
    now = datetime.now(UTC)
    return OutboxEvent(
        id=uuid4(),
        account_id=uuid4(),
        aggregate_type="context_source",
        aggregate_id=uuid4(),
        event_type="context_added.v1",
        payload={"correlationId": str(uuid4()), "jobId": str(uuid4())},
        status="pending",
        attempt_count=attempt_count,
        available_at=now,
        created_at=now,
        published_at=None,
    )


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_relay_marks_event_after_publish() -> None:
    event = _event()
    publisher = FakePublisher()
    outbox = FakeOutbox(event)
    unit_of_work = FakeUnitOfWork(outbox)
    stream = StringIO()
    relay = OutboxRelay(publisher, lambda: unit_of_work, _logger(stream))

    async def scenario() -> None:
        with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
            await relay.publish(event)

    asyncio.run(scenario())
    assert [published.id for published in publisher.events] == [event.id]
    assert outbox.event.status == "published"
    assert unit_of_work.commits == 1
    logs = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [log["event_name"] for log in logs] == [
        "outbox.relay_started",
        "outbox.publish_succeeded",
    ]
    assert logs[0]["outbox_event_id"] == str(event.id)
    assert logs[0]["aggregate_id"] == str(event.aggregate_id)
    assert "correlationId" not in stream.getvalue()


def test_mark_failure_keeps_event_pending_for_recovery() -> None:
    event = _event()
    publisher = FakePublisher()
    outbox = FakeOutbox(event, fail_mark=True)
    unit_of_work = FakeUnitOfWork(outbox)
    stream = StringIO()
    relay = OutboxRelay(publisher, lambda: unit_of_work, _logger(stream))

    async def scenario() -> None:
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
        ), pytest.raises(JobsRepositoryError):
            await relay.publish(event)

    asyncio.run(scenario())
    assert len(publisher.events) == 1
    assert outbox.event.status == "pending"
    assert unit_of_work.commits == 0
    assert '"event_name":"outbox.mark_published_failed"' in stream.getvalue()


def test_republish_uses_the_same_stable_event_identifier() -> None:
    event = _event(attempt_count=1)
    publisher = FakePublisher()
    outbox = FakeOutbox(event)
    unit_of_work = FakeUnitOfWork(outbox)
    stream = StringIO()
    relay = OutboxRelay(publisher, lambda: unit_of_work, _logger(stream))

    async def scenario() -> None:
        with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
            await relay.publish(event)
            await relay.publish(event)

    asyncio.run(scenario())
    assert [published.id for published in publisher.events] == [event.id, event.id]
    assert stream.getvalue().count('"event_name":"outbox.republished"') == 2
