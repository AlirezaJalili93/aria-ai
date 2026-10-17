from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.scope_generation import (
    ScopeGenerationCommand,
    ScopeGenerationError,
    ScopeGenerationRepositoryError,
    ScopeGenerationResult,
    ScopeInputRevision,
)
from aria_observability import StructuredEventLogger, TraceContext, bind_trace_context

from app.application.ports import (
    JobExecutionGuard,
    JobExecutionGuardPersistenceError,
    JobExecutionGuardValidationError,
)

SCOPE_GENERATION_MESSAGE_VERSION = "1"
SCOPE_GENERATION_JOB_TYPE = "scope_generation"
SCOPE_GENERATION_EVENT_TYPE = "scope.generation_requested.v1"


class ScopeGenerationMessageValidationError(ValueError):
    """Identifier-only AI-05 message or durable references are invalid."""


class ScopeGenerationRuntimePersistenceError(RuntimeError):
    """The same AI-05 Job remains recoverable after persistence failure."""


class ScopeGenerationSyntheticFixtureRequired(ValueError):
    """Worker execution is not authorized for this synthetic Project."""


@dataclass(frozen=True, slots=True)
class ScopeGenerationJobMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    @classmethod
    def from_payload(cls, payload: object) -> ScopeGenerationJobMessage:
        if not isinstance(payload, Mapping) or set(payload) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise ScopeGenerationMessageValidationError("Invalid AI-05 message shape")
        try:
            value = cls(
                message_version=str(payload["message_version"]),
                outbox_event_id=UUID(str(payload["outbox_event_id"])),
                job_id=UUID(str(payload["job_id"])),
            )
        except (TypeError, ValueError):
            raise ScopeGenerationMessageValidationError(
                "Invalid AI-05 message identifiers"
            ) from None
        if value.message_version != SCOPE_GENERATION_MESSAGE_VERSION:
            raise ScopeGenerationMessageValidationError("Unsupported AI-05 message version")
        return value


@dataclass(frozen=True, slots=True)
class ScopeGenerationJobInput:
    job_id: UUID
    account_id: UUID
    project_id: UUID
    correlation_id: UUID
    context_version: int
    context_item_revisions: tuple[ScopeInputRevision, ...]
    requirement_revisions: tuple[ScopeInputRevision, ...]
    gap_revisions: tuple[ScopeInputRevision, ...]
    first_attempt: bool


@dataclass(frozen=True, slots=True)
class ScopeGenerationConsumerResult:
    status: Literal["succeeded", "failed", "suppressed", "already_completed"]
    error_code: str | None = None


class ScopeGenerationJobStore(Protocol):
    async def prepare(self, message: ScopeGenerationJobMessage) -> ScopeGenerationJobInput: ...

    async def finalize_failure(self, job: ScopeGenerationJobInput, *, error_code: str) -> None: ...


class ScopeGenerationCommandFactory(Protocol):
    def build(self, job: ScopeGenerationJobInput) -> ScopeGenerationCommand: ...


class ScopeGenerationUseCaseProtocol(Protocol):
    async def execute(self, command: ScopeGenerationCommand) -> ScopeGenerationResult: ...


class SyntheticScopeAuthorizer(Protocol):
    def allows(self, *, account_id: UUID, project_id: UUID) -> bool: ...


class DenyAllSyntheticScopeProjects:
    def allows(self, *, account_id: UUID, project_id: UUID) -> bool:
        del account_id, project_id
        return False


class ExplicitSyntheticScopeProjects:
    def __init__(self, approved: frozenset[tuple[UUID, UUID]]) -> None:
        self._approved = approved

    def allows(self, *, account_id: UUID, project_id: UUID) -> bool:
        return (account_id, project_id) in self._approved


class ScopeGenerationConsumer:
    def __init__(
        self,
        *,
        guard: JobExecutionGuard,
        store: ScopeGenerationJobStore,
        command_factory: ScopeGenerationCommandFactory,
        use_case: ScopeGenerationUseCaseProtocol,
        synthetic_authorizer: SyntheticScopeAuthorizer,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._guard = guard
        self._store = store
        self._command_factory = command_factory
        self._use_case = use_case
        self._synthetic_authorizer = synthetic_authorizer
        self._event_logger = event_logger

    async def execute(self, message: ScopeGenerationJobMessage) -> ScopeGenerationConsumerResult:
        try:
            acquisition = await self._guard.acquire(message.job_id)
        except JobExecutionGuardValidationError:
            raise ScopeGenerationMessageValidationError(
                "Scope Generation Job is not available"
            ) from None
        except JobExecutionGuardPersistenceError:
            raise ScopeGenerationRuntimePersistenceError from None
        if acquisition == "already_in_progress":
            self._event_logger.emit(
                "worker.job_duplicate_suppressed",
                job_id=str(message.job_id),
                task_type=SCOPE_GENERATION_JOB_TYPE,
                reason_code="already_in_progress",
                status="suppressed",
            )
            return ScopeGenerationConsumerResult(status="suppressed")
        if acquisition == "already_completed":
            self._event_logger.emit(
                "worker.job_already_completed",
                job_id=str(message.job_id),
                task_type=SCOPE_GENERATION_JOB_TYPE,
                reason_code="already_completed",
                status="succeeded",
            )
            return ScopeGenerationConsumerResult(status="already_completed")

        job: ScopeGenerationJobInput | None = None
        try:
            job = await self._store.prepare(message)
            if not self._synthetic_authorizer.allows(
                account_id=job.account_id, project_id=job.project_id
            ):
                raise ScopeGenerationSyntheticFixtureRequired
            with _job_trace(job):
                command = self._command_factory.build(job)
                _require_matching_command(job, command)
                await self._use_case.execute(command)
            await self._guard.complete(job.job_id)
            self._event_logger.emit(
                "worker.job_execution_completed",
                job_id=str(job.job_id),
                task_type=SCOPE_GENERATION_JOB_TYPE,
                status="succeeded",
            )
            return ScopeGenerationConsumerResult(status="succeeded")
        except (ScopeGenerationRepositoryError, ScopeGenerationRuntimePersistenceError):
            await self._guard.release(message.job_id)
            trace = _job_trace(job) if job is not None else nullcontext()
            with trace:
                self._event_logger.emit(
                    "worker.job_execution_interrupted",
                    level="ERROR",
                    job_id=str(message.job_id),
                    task_type=SCOPE_GENERATION_JOB_TYPE,
                    reason_code="persistence_unavailable",
                    error_code="SCOPE_GENERATION_PERSISTENCE_UNAVAILABLE",
                    status="recoverable",
                )
            raise ScopeGenerationRuntimePersistenceError from None
        except (ScopeGenerationError, ScopeGenerationSyntheticFixtureRequired) as error:
            assert job is not None
            error_code = (
                error.reason_code
                if isinstance(error, ScopeGenerationError)
                else "SYNTHETIC_FIXTURE_REQUIRED"
            )
            try:
                await self._store.finalize_failure(job, error_code=error_code)
            except ScopeGenerationRuntimePersistenceError:
                await self._guard.release(message.job_id)
                raise
            await self._guard.complete(message.job_id)
            return ScopeGenerationConsumerResult(status="failed", error_code=error_code)
        except BaseException:
            await self._guard.release(message.job_id)
            raise


def _require_matching_command(
    job: ScopeGenerationJobInput, command: ScopeGenerationCommand
) -> None:
    if (
        command.job_id != job.job_id
        or command.account_id != job.account_id
        or command.project_id != job.project_id
        or command.correlation_id != job.correlation_id
        or command.context_version != job.context_version
        or command.context_item_revisions != job.context_item_revisions
        or command.requirement_revisions != job.requirement_revisions
        or command.gap_revisions != job.gap_revisions
        or command.task_type != SCOPE_GENERATION_JOB_TYPE
    ):
        raise ScopeGenerationMessageValidationError("AI-05 command identity is invalid")


def _job_trace(job: ScopeGenerationJobInput) -> AbstractContextManager[None]:
    return bind_trace_context(
        TraceContext(
            correlation_id=str(job.correlation_id),
            account_id=str(job.account_id),
            project_id=str(job.project_id),
            job_id=str(job.job_id),
        )
    )
