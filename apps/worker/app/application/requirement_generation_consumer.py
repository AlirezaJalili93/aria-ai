from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.requirements_generation import (
    ContextItemRevision,
    GenerateRequirementsCommand,
    GenerateRequirementsUseCaseProtocol,
    RequirementGenerationError,
    RequirementGenerationRepositoryError,
)
from aria_observability import StructuredEventLogger, TraceContext, bind_trace_context

from app.application.ports import (
    JobExecutionGuard,
    JobExecutionGuardPersistenceError,
    JobExecutionGuardValidationError,
)

REQUIREMENT_GENERATION_MESSAGE_VERSION = "1"
REQUIREMENT_GENERATION_JOB_TYPE = "requirement_generation"
REQUIREMENT_GENERATION_EVENT_TYPE = "requirement.generation_requested.v1"


class RequirementGenerationMessageValidationError(ValueError):
    """The identifier-only AI-02 message or its durable references are invalid."""


class RequirementGenerationRuntimePersistenceError(RuntimeError):
    """The AI-02 Job remains recoverable after a persistence interruption."""


@dataclass(frozen=True, slots=True)
class RequirementGenerationJobMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    @classmethod
    def from_payload(cls, payload: object) -> RequirementGenerationJobMessage:
        if not isinstance(payload, Mapping) or set(payload) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise RequirementGenerationMessageValidationError("Invalid AI-02 message shape")
        try:
            value = cls(
                message_version=str(payload["message_version"]),
                outbox_event_id=UUID(str(payload["outbox_event_id"])),
                job_id=UUID(str(payload["job_id"])),
            )
        except (TypeError, ValueError):
            raise RequirementGenerationMessageValidationError(
                "Invalid AI-02 message identifiers"
            ) from None
        if value.message_version != REQUIREMENT_GENERATION_MESSAGE_VERSION:
            raise RequirementGenerationMessageValidationError("Unsupported AI-02 message version")
        return value


@dataclass(frozen=True, slots=True)
class RequirementGenerationJobInput:
    job_id: UUID
    account_id: UUID
    project_id: UUID
    correlation_id: UUID
    context_version: int
    context_item_revisions: tuple[ContextItemRevision, ...]
    first_attempt: bool


@dataclass(frozen=True, slots=True)
class RequirementGenerationConsumerResult:
    status: Literal["succeeded", "failed", "suppressed", "already_completed"]
    error_code: str | None = None


class RequirementGenerationJobStore(Protocol):
    async def prepare(
        self, message: RequirementGenerationJobMessage
    ) -> RequirementGenerationJobInput: ...

    async def finalize_failure(
        self, job: RequirementGenerationJobInput, *, error_code: str
    ) -> None: ...


class RequirementGenerationCommandFactory(Protocol):
    def build(self, job: RequirementGenerationJobInput) -> GenerateRequirementsCommand: ...


class RequirementGenerationConsumer:
    def __init__(
        self,
        *,
        guard: JobExecutionGuard,
        store: RequirementGenerationJobStore,
        command_factory: RequirementGenerationCommandFactory,
        use_case: GenerateRequirementsUseCaseProtocol,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._guard = guard
        self._store = store
        self._command_factory = command_factory
        self._use_case = use_case
        self._event_logger = event_logger

    async def execute(
        self, message: RequirementGenerationJobMessage
    ) -> RequirementGenerationConsumerResult:
        try:
            acquisition = await self._guard.acquire(message.job_id)
        except JobExecutionGuardValidationError:
            raise RequirementGenerationMessageValidationError(
                "Requirement Generation Job is not available"
            ) from None
        except JobExecutionGuardPersistenceError:
            raise RequirementGenerationRuntimePersistenceError from None
        if acquisition == "already_in_progress":
            self._event_logger.emit(
                "worker.job_duplicate_suppressed",
                job_id=str(message.job_id),
                task_type=REQUIREMENT_GENERATION_JOB_TYPE,
                reason_code="already_in_progress",
                status="suppressed",
            )
            return RequirementGenerationConsumerResult(status="suppressed")
        if acquisition == "already_completed":
            self._event_logger.emit(
                "worker.job_already_completed",
                job_id=str(message.job_id),
                task_type=REQUIREMENT_GENERATION_JOB_TYPE,
                reason_code="already_completed",
                status="succeeded",
            )
            return RequirementGenerationConsumerResult(status="already_completed")

        job: RequirementGenerationJobInput | None = None
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
                task_type=REQUIREMENT_GENERATION_JOB_TYPE,
                status="succeeded",
            )
            return RequirementGenerationConsumerResult(status="succeeded")
        except (
            RequirementGenerationRepositoryError,
            RequirementGenerationRuntimePersistenceError,
        ):
            await self._guard.release(message.job_id)
            trace = _job_trace(job) if job is not None else nullcontext()
            with trace:
                self._event_logger.emit(
                    "worker.job_execution_interrupted",
                    level="ERROR",
                    job_id=str(message.job_id),
                    task_type=REQUIREMENT_GENERATION_JOB_TYPE,
                    reason_code="persistence_unavailable",
                    error_code="REQUIREMENT_GENERATION_PERSISTENCE_UNAVAILABLE",
                    status="recoverable",
                )
            raise RequirementGenerationRuntimePersistenceError from None
        except RequirementGenerationError as error:
            assert job is not None
            error_code = _safe_error_code(error)
            try:
                await self._store.finalize_failure(job, error_code=error_code)
            except RequirementGenerationRuntimePersistenceError:
                await self._guard.release(message.job_id)
                raise
            await self._guard.complete(message.job_id)
            return RequirementGenerationConsumerResult(
                status="failed", error_code=error_code
            )
        except BaseException:
            await self._guard.release(message.job_id)
            raise


def _require_matching_command(
    job: RequirementGenerationJobInput, command: GenerateRequirementsCommand
) -> None:
    if (
        command.job_id != job.job_id
        or command.account_id != job.account_id
        or command.project_id != job.project_id
        or command.correlation_id != job.correlation_id
        or command.context_version != job.context_version
        or command.context_item_revisions != job.context_item_revisions
        or command.task_type != REQUIREMENT_GENERATION_JOB_TYPE
    ):
        raise RequirementGenerationMessageValidationError("AI-02 command identity is invalid")


def _safe_error_code(error: RequirementGenerationError) -> str:
    code = getattr(error, "code", None)
    return str(code or error.reason_code).upper()


def _job_trace(job: RequirementGenerationJobInput) -> AbstractContextManager[None]:
    return bind_trace_context(
        TraceContext(
            correlation_id=str(job.correlation_id),
            account_id=str(job.account_id),
            project_id=str(job.project_id),
            job_id=str(job.job_id),
        )
    )
