from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.gap_detection import (
    ContextItemRevision,
    DetectGapsCommand,
    GapDetectionError,
    GapDetectionRepositoryError,
    GapDetectionResult,
    RequirementRevision,
)
from aria_observability import StructuredEventLogger, TraceContext, bind_trace_context

from app.application.ports import (
    JobExecutionGuard,
    JobExecutionGuardPersistenceError,
    JobExecutionGuardValidationError,
)

GAP_DETECTION_MESSAGE_VERSION = "1"
GAP_DETECTION_JOB_TYPE = "gap_detection"
GAP_DETECTION_EVENT_TYPE = "gap.detection_requested.v1"


class GapDetectionMessageValidationError(ValueError):
    """The identifier-only AI-03 message or durable references are invalid."""


class GapDetectionRuntimePersistenceError(RuntimeError):
    """The AI-03 Job remains recoverable after a persistence interruption."""


@dataclass(frozen=True, slots=True)
class GapDetectionJobMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    @classmethod
    def from_payload(cls, payload: object) -> GapDetectionJobMessage:
        if not isinstance(payload, Mapping) or set(payload) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise GapDetectionMessageValidationError("Invalid AI-03 message shape")
        try:
            value = cls(
                message_version=str(payload["message_version"]),
                outbox_event_id=UUID(str(payload["outbox_event_id"])),
                job_id=UUID(str(payload["job_id"])),
            )
        except (TypeError, ValueError):
            raise GapDetectionMessageValidationError(
                "Invalid AI-03 message identifiers"
            ) from None
        if value.message_version != GAP_DETECTION_MESSAGE_VERSION:
            raise GapDetectionMessageValidationError("Unsupported AI-03 message version")
        return value


@dataclass(frozen=True, slots=True)
class GapDetectionJobInput:
    job_id: UUID
    account_id: UUID
    project_id: UUID
    correlation_id: UUID
    context_version: int
    context_item_revisions: tuple[ContextItemRevision, ...]
    requirement_revisions: tuple[RequirementRevision, ...]
    completion_checklist_version: str
    critical_rule_pack_version: str
    first_attempt: bool


@dataclass(frozen=True, slots=True)
class GapDetectionConsumerResult:
    status: Literal["succeeded", "failed", "suppressed", "already_completed"]
    error_code: str | None = None


class GapDetectionJobStore(Protocol):
    async def prepare(self, message: GapDetectionJobMessage) -> GapDetectionJobInput: ...

    async def finalize_failure(
        self, job: GapDetectionJobInput, *, error_code: str
    ) -> None: ...


class GapDetectionCommandFactory(Protocol):
    def build(self, job: GapDetectionJobInput) -> DetectGapsCommand: ...


class DetectGapsUseCaseProtocol(Protocol):
    async def execute(self, command: DetectGapsCommand) -> GapDetectionResult: ...


class GapDetectionConsumer:
    def __init__(
        self,
        *,
        guard: JobExecutionGuard,
        store: GapDetectionJobStore,
        command_factory: GapDetectionCommandFactory,
        use_case: DetectGapsUseCaseProtocol,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._guard = guard
        self._store = store
        self._command_factory = command_factory
        self._use_case = use_case
        self._event_logger = event_logger

    async def execute(self, message: GapDetectionJobMessage) -> GapDetectionConsumerResult:
        try:
            acquisition = await self._guard.acquire(message.job_id)
        except JobExecutionGuardValidationError:
            raise GapDetectionMessageValidationError(
                "Gap Detection Job is not available"
            ) from None
        except JobExecutionGuardPersistenceError:
            raise GapDetectionRuntimePersistenceError from None
        if acquisition == "already_in_progress":
            self._event_logger.emit(
                "worker.job_duplicate_suppressed",
                job_id=str(message.job_id),
                task_type=GAP_DETECTION_JOB_TYPE,
                reason_code="already_in_progress",
                status="suppressed",
            )
            return GapDetectionConsumerResult(status="suppressed")
        if acquisition == "already_completed":
            self._event_logger.emit(
                "worker.job_already_completed",
                job_id=str(message.job_id),
                task_type=GAP_DETECTION_JOB_TYPE,
                reason_code="already_completed",
                status="succeeded",
            )
            return GapDetectionConsumerResult(status="already_completed")

        job: GapDetectionJobInput | None = None
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
                task_type=GAP_DETECTION_JOB_TYPE,
                status="succeeded",
            )
            return GapDetectionConsumerResult(status="succeeded")
        except (GapDetectionRepositoryError, GapDetectionRuntimePersistenceError):
            await self._guard.release(message.job_id)
            trace = _job_trace(job) if job is not None else nullcontext()
            with trace:
                self._event_logger.emit(
                    "worker.job_execution_interrupted",
                    level="ERROR",
                    job_id=str(message.job_id),
                    task_type=GAP_DETECTION_JOB_TYPE,
                    reason_code="persistence_unavailable",
                    error_code="GAP_DETECTION_PERSISTENCE_UNAVAILABLE",
                    status="recoverable",
                )
            raise GapDetectionRuntimePersistenceError from None
        except GapDetectionError as error:
            assert job is not None
            error_code = _safe_error_code(error)
            try:
                await self._store.finalize_failure(job, error_code=error_code)
            except GapDetectionRuntimePersistenceError:
                await self._guard.release(message.job_id)
                raise
            await self._guard.complete(message.job_id)
            return GapDetectionConsumerResult(status="failed", error_code=error_code)
        except BaseException:
            await self._guard.release(message.job_id)
            raise


def _require_matching_command(
    job: GapDetectionJobInput, command: DetectGapsCommand
) -> None:
    if (
        command.job_id != job.job_id
        or command.account_id != job.account_id
        or command.project_id != job.project_id
        or command.correlation_id != job.correlation_id
        or command.context_version != job.context_version
        or command.context_item_revisions != job.context_item_revisions
        or command.requirement_revisions != job.requirement_revisions
        or command.completion_checklist_version != job.completion_checklist_version
        or command.critical_rule_pack_version != job.critical_rule_pack_version
        or command.task_type != GAP_DETECTION_JOB_TYPE
    ):
        raise GapDetectionMessageValidationError("AI-03 command identity is invalid")


def _safe_error_code(error: GapDetectionError) -> str:
    code = getattr(error, "code", None)
    return str(code or error.reason_code).upper()


def _job_trace(job: GapDetectionJobInput) -> AbstractContextManager[None]:
    return bind_trace_context(
        TraceContext(
            correlation_id=str(job.correlation_id),
            account_id=str(job.account_id),
            project_id=str(job.project_id),
            job_id=str(job.job_id),
        )
    )
