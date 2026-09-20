from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from aria_observability import (
    NoOpOperationalMetrics,
    OperationalMetrics,
    StructuredEventLogger,
    TraceContext,
    bind_trace_context,
    current_trace_context,
)

from app.application.ports import ExecutionAcquisition, JobExecutionGuard


@dataclass(frozen=True, slots=True)
class JobExecutionContext:
    job_id: UUID
    account_id: UUID | None
    project_id: UUID | None
    correlation_id: UUID
    task_type: str | None


class JobExecutionCoordinator:
    """Coordinate one delivery without choosing Queue or PostgreSQL lock mechanics."""

    def __init__(
        self,
        guard: JobExecutionGuard,
        event_logger: StructuredEventLogger,
        operational_metrics: OperationalMetrics | None = None,
    ) -> None:
        self._guard = guard
        self._event_logger = event_logger
        self._operational_metrics = operational_metrics or NoOpOperationalMetrics()

    async def execute(
        self,
        context: JobExecutionContext,
        handler: Callable[[], Awaitable[None]],
    ) -> ExecutionAcquisition:
        started_at = perf_counter()
        with _execution_trace(context):
            acquisition = await self._guard.acquire(context.job_id)
            if acquisition == "already_completed":
                self._event_logger.emit(
                    "worker.job_already_completed",
                    job_id=str(context.job_id),
                    task_type=context.task_type,
                    reason_code="already_completed",
                    duration_ms=(perf_counter() - started_at) * 1000,
                    status="succeeded",
                )
                return acquisition
            if acquisition == "already_in_progress":
                self._event_logger.emit(
                    "worker.job_duplicate_suppressed",
                    job_id=str(context.job_id),
                    task_type=context.task_type,
                    reason_code="already_in_progress",
                    duration_ms=(perf_counter() - started_at) * 1000,
                    status="suppressed",
                )
                return acquisition

            self._event_logger.emit(
                "worker.job_guard_acquired",
                job_id=str(context.job_id),
                task_type=context.task_type,
                reason_code="acquired",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="acquired",
            )
            self._event_logger.emit(
                "worker.job_execution_started",
                job_id=str(context.job_id),
                task_type=context.task_type,
                reason_code="acquired",
                status="running",
            )
            try:
                await handler()
                await self._guard.complete(context.job_id)
            except BaseException:
                await self._guard.release(context.job_id)
                self._record_job_metric(context, "failed", started_at)
                self._event_logger.emit(
                    "worker.job_execution_interrupted",
                    level="ERROR",
                    job_id=str(context.job_id),
                    task_type=context.task_type,
                    reason_code="execution_interrupted",
                    duration_ms=(perf_counter() - started_at) * 1000,
                    status="interrupted",
                )
                raise

            self._record_job_metric(context, "succeeded", started_at)
            return acquisition

    def _record_job_metric(
        self, context: JobExecutionContext, status: str, started_at: float
    ) -> None:
        if context.task_type is None:
            return
        with suppress(Exception):
            self._operational_metrics.record_worker_job(
                job_type=context.task_type,
                status=status,
                duration_ms=(perf_counter() - started_at) * 1000,
            )


@contextmanager
def _execution_trace(context: JobExecutionContext) -> Iterator[None]:
    current = current_trace_context()
    trace_context = TraceContext(
        correlation_id=str(context.correlation_id),
        request_id=current.request_id if current else None,
        account_id=str(context.account_id) if context.account_id is not None else None,
        project_id=str(context.project_id) if context.project_id is not None else None,
        job_id=str(context.job_id),
    )
    with bind_trace_context(trace_context):
        yield
