from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from aria_observability import (
    StructuredEventLogger,
    TraceContext,
    bind_trace_context,
    current_trace_context,
)

from app.modules.jobs.application.ports import JobsUnitOfWorkFactory, QueuePublisher
from app.modules.jobs.domain.job import OutboxEvent


class OutboxRelay:
    """Publish one committed event, then acknowledge it in PostgreSQL.

    Selection, batching, scheduling, leasing and transport wiring deliberately remain outside
    this partial contract. A mark failure leaves the durable row pending, so a later invocation
    may publish the same stable event identifier again.
    """

    def __init__(
        self,
        publisher: QueuePublisher,
        unit_of_work_factory: JobsUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._publisher = publisher
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._clock = clock

    async def publish(self, event: OutboxEvent) -> None:
        started_at = perf_counter()
        attempt = event.attempt_count + 1
        with _event_trace(event):
            self._event_logger.emit(
                "outbox.relay_started",
                outbox_event_id=str(event.id),
                aggregate_type=event.aggregate_type,
                aggregate_id=str(event.aggregate_id),
                attempt=attempt,
                status=event.status,
            )
            if event.attempt_count > 0:
                self._event_logger.emit(
                    "outbox.republished",
                    outbox_event_id=str(event.id),
                    aggregate_type=event.aggregate_type,
                    aggregate_id=str(event.aggregate_id),
                    attempt=attempt,
                    status=event.status,
                )

            try:
                await self._publisher.publish(event)
            except Exception:
                self._event_logger.emit(
                    "outbox.publish_failed",
                    level="ERROR",
                    outbox_event_id=str(event.id),
                    aggregate_type=event.aggregate_type,
                    aggregate_id=str(event.aggregate_id),
                    attempt=attempt,
                    duration_ms=(perf_counter() - started_at) * 1000,
                    error_code="OUTBOX_PUBLISH_FAILED",
                    status="failed",
                )
                raise

            self._event_logger.emit(
                "outbox.publish_succeeded",
                outbox_event_id=str(event.id),
                aggregate_type=event.aggregate_type,
                aggregate_id=str(event.aggregate_id),
                attempt=attempt,
                duration_ms=(perf_counter() - started_at) * 1000,
                status="published",
            )

            try:
                async with self._unit_of_work_factory() as unit_of_work:
                    await unit_of_work.outbox.mark_published(event.id, self._clock())
                    await unit_of_work.commit()
            except Exception:
                self._event_logger.emit(
                    "outbox.mark_published_failed",
                    level="ERROR",
                    outbox_event_id=str(event.id),
                    aggregate_type=event.aggregate_type,
                    aggregate_id=str(event.aggregate_id),
                    attempt=attempt,
                    duration_ms=(perf_counter() - started_at) * 1000,
                    error_code="OUTBOX_MARK_PUBLISHED_FAILED",
                    status="pending",
                )
                raise


@contextmanager
def _event_trace(event: OutboxEvent) -> Iterator[None]:
    correlation_id = _payload_uuid(event.payload.get("correlationId"))
    if correlation_id is None:
        yield
        return

    current = current_trace_context()
    context = TraceContext(
        correlation_id=correlation_id,
        request_id=current.request_id if current else None,
        account_id=str(event.account_id) if event.account_id is not None else None,
        project_id=current.project_id if current else None,
        job_id=current.job_id if current else None,
    )
    with bind_trace_context(context):
        yield


def _payload_uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None
