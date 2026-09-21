from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.context_structuring import (
    ContextStructuringCommand,
    ContextStructuringError,
    ContextStructuringRepositoryError,
    ContextStructuringUseCaseProtocol,
)
from aria_observability import StructuredEventLogger, TraceContext, bind_trace_context

from app.application.ports import (
    JobExecutionGuard,
    JobExecutionGuardPersistenceError,
    JobExecutionGuardValidationError,
)

CONTEXT_STRUCTURING_MESSAGE_VERSION = "1"
CONTEXT_STRUCTURING_JOB_TYPE = "context_structuring"
CONTEXT_STRUCTURING_EVENT_TYPE = "context.structuring_requested.v1"


class ContextStructuringMessageValidationError(RuntimeError):
    """The Queue delivery does not match the frozen AI-01 envelope."""


class ContextStructuringRuntimePersistenceError(RuntimeError):
    """AI-01 preparation or finalization did not commit."""


@dataclass(frozen=True, slots=True)
class ContextStructuringJobMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    def __post_init__(self) -> None:
        if self.message_version != CONTEXT_STRUCTURING_MESSAGE_VERSION:
            raise ContextStructuringMessageValidationError("Unsupported message version")

    @classmethod
    def from_payload(cls, payload: object) -> ContextStructuringJobMessage:
        if not isinstance(payload, dict) or set(payload) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise ContextStructuringMessageValidationError("Message shape is invalid")
        try:
            return cls(
                message_version=str(payload["message_version"]),
                outbox_event_id=UUID(str(payload["outbox_event_id"])),
                job_id=UUID(str(payload["job_id"])),
            )
        except (TypeError, ValueError):
            raise ContextStructuringMessageValidationError(
                "Message values are invalid"
            ) from None


@dataclass(frozen=True, slots=True)
class ContextStructuringJobInput:
    job_id: UUID
    account_id: UUID
    project_id: UUID
    correlation_id: UUID
    first_attempt: bool


@dataclass(frozen=True, slots=True)
class ContextStructuringConsumerResult:
    status: Literal["succeeded", "failed", "suppressed", "already_completed"]
    error_code: str | None = None


class ContextStructuringJobStore(Protocol):
    async def prepare(
        self, message: ContextStructuringJobMessage
    ) -> ContextStructuringJobInput: ...

    async def finalize_failure(
        self,
        job: ContextStructuringJobInput,
        *,
        error_code: str,
    ) -> None: ...


class ContextStructuringCommandFactory(Protocol):
    def build(self, job: ContextStructuringJobInput) -> ContextStructuringCommand: ...


class ContextStructuringConsumer:
    def __init__(
        self,
        *,
        guard: JobExecutionGuard,
        store: ContextStructuringJobStore,
        command_factory: ContextStructuringCommandFactory,
        use_case: ContextStructuringUseCaseProtocol,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._guard = guard
        self._store = store
        self._command_factory = command_factory
        self._use_case = use_case
        self._event_logger = event_logger

    async def execute(
        self, message: ContextStructuringJobMessage
    ) -> ContextStructuringConsumerResult:
        try:
            acquisition = await self._guard.acquire(message.job_id)
        except JobExecutionGuardValidationError:
            raise ContextStructuringMessageValidationError(
                "Context Structuring Job is not available"
            ) from None
        except JobExecutionGuardPersistenceError:
            raise ContextStructuringRuntimePersistenceError from None
        if acquisition == "already_in_progress":
            self._event_logger.emit(
                "worker.job_duplicate_suppressed",
                job_id=str(message.job_id),
                task_type=CONTEXT_STRUCTURING_JOB_TYPE,
                reason_code="already_in_progress",
                status="suppressed",
            )
            return ContextStructuringConsumerResult(status="suppressed")
        if acquisition == "already_completed":
            self._event_logger.emit(
                "worker.job_already_completed",
                job_id=str(message.job_id),
                task_type=CONTEXT_STRUCTURING_JOB_TYPE,
                reason_code="already_completed",
                status="succeeded",
            )
            return ContextStructuringConsumerResult(status="already_completed")

        job: ContextStructuringJobInput | None = None
        try:
            job = await self._store.prepare(message)
            with _job_trace(job):
                command = self._command_factory.build(job)
                _require_matching_command(job, command)
                await self._use_case.execute(command)
            await self._guard.complete(job.job_id)
            self._event_logger.emit(
                "worker.job_execution_completed",
                job_id=str(job.job_id),
                task_type=CONTEXT_STRUCTURING_JOB_TYPE,
                status="succeeded",
            )
            return ContextStructuringConsumerResult(status="succeeded")
        except (ContextStructuringRepositoryError, ContextStructuringRuntimePersistenceError):
            await self._guard.release(message.job_id)
            trace = _job_trace(job) if job is not None else nullcontext()
            with trace:
                self._event_logger.emit(
                    "worker.job_execution_interrupted",
                    level="ERROR",
                    job_id=str(message.job_id),
                    task_type=CONTEXT_STRUCTURING_JOB_TYPE,
                    reason_code="persistence_unavailable",
                    error_code="CONTEXT_STRUCTURING_PERSISTENCE_UNAVAILABLE",
                    status="recoverable",
                )
            raise ContextStructuringRuntimePersistenceError from None
        except ContextStructuringError as error:
            assert job is not None
            error_code = _safe_error_code(error)
            try:
                await self._store.finalize_failure(job, error_code=error_code)
            except ContextStructuringRuntimePersistenceError:
                await self._guard.release(message.job_id)
                raise
            await self._guard.complete(message.job_id)
            return ContextStructuringConsumerResult(
                status="failed",
                error_code=error_code,
            )
        except BaseException:
            await self._guard.release(message.job_id)
            raise


def _require_matching_command(
    job: ContextStructuringJobInput,
    command: ContextStructuringCommand,
) -> None:
    if (
        command.job_id != job.job_id
        or command.account_id != job.account_id
        or command.project_id != job.project_id
        or command.correlation_id != job.correlation_id
        or command.task_type != CONTEXT_STRUCTURING_JOB_TYPE
    ):
        raise ContextStructuringMessageValidationError("Command identity is invalid")


def _safe_error_code(error: ContextStructuringError) -> str:
    return error.reason_code.upper()


def _job_trace(job: ContextStructuringJobInput) -> AbstractContextManager[None]:
    return bind_trace_context(
        TraceContext(
            correlation_id=str(job.correlation_id),
            account_id=str(job.account_id),
            project_id=str(job.project_id),
            job_id=str(job.job_id),
        )
    )
