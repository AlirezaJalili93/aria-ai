from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID, uuid4

from aria_backend_application.requirements_generation import (
    RequirementContextSnapshotReader,
    RequirementGenerationRepositoryError,
)
from aria_observability import StructuredEventLogger

from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

REQUIREMENT_GENERATION_JOB_TYPE = "requirement_generation"
REQUIREMENT_GENERATION_EVENT_TYPE = "requirement.generation_requested.v1"
REQUIREMENT_GENERATION_PAYLOAD_VERSION = "1"
REQUIREMENT_GENERATION_AUTOMATIC_QUEUE_RETRY = False
REQUIREMENT_GENERATION_JOB_MAX_ATTEMPTS = 1


class RequirementGenerationSchedulingError(RuntimeError):
    """A safe internal AI-02 scheduling failure."""


class RequirementGenerationSyntheticFixtureRequired(RequirementGenerationSchedulingError):
    """The project is not explicitly approved for synthetic execution."""


class RequirementGenerationContextRequired(RequirementGenerationSchedulingError):
    """The exact Context revision is unavailable or empty."""


class RequirementGenerationActiveJobConflict(RequirementGenerationSchedulingError):
    """Another active AI-02 Job targets the same Context version."""


class SyntheticRequirementGenerationAuthorizer(Protocol):
    def allows(self, *, account_id: UUID, project_id: UUID) -> bool: ...


class DenyAllSyntheticRequirementGeneration:
    def allows(self, *, account_id: UUID, project_id: UUID) -> bool:
        del account_id, project_id
        return False


class ExplicitSyntheticRequirementGenerationProjects:
    def __init__(self, approved: frozenset[tuple[UUID, UUID]]) -> None:
        self._approved = approved

    def allows(self, *, account_id: UUID, project_id: UUID) -> bool:
        return (account_id, project_id) in self._approved


class RequirementGenerationJobUnitOfWork(Protocol):
    @property
    def jobs(self) -> JobRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class RequirementGenerationJobUnitOfWorkFactory(Protocol):
    def __call__(self) -> RequirementGenerationJobUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class ScheduleRequirementGenerationCommand:
    account_id: UUID
    project_id: UUID
    context_version: int
    correlation_id: UUID

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("context_version must be at least one")


@dataclass(frozen=True, slots=True)
class RequirementGenerationScheduled:
    job_id: UUID
    outbox_event_id: UUID


class ScheduleRequirementGenerationUseCase:
    """Internal-only scheduler for explicitly approved synthetic AI-02 fixtures."""

    def __init__(
        self,
        *,
        snapshot_reader: RequirementContextSnapshotReader,
        unit_of_work_factory: RequirementGenerationJobUnitOfWorkFactory,
        synthetic_authorizer: SyntheticRequirementGenerationAuthorizer,
        event_logger: StructuredEventLogger,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._unit_of_work_factory = unit_of_work_factory
        self._synthetic_authorizer = synthetic_authorizer
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(
        self, command: ScheduleRequirementGenerationCommand
    ) -> RequirementGenerationScheduled:
        if not self._synthetic_authorizer.allows(
            account_id=command.account_id, project_id=command.project_id
        ):
            raise RequirementGenerationSyntheticFixtureRequired
        snapshot = await self._snapshot_reader.resolve_exact(
            account_id=command.account_id,
            project_id=command.project_id,
            context_version=command.context_version,
        )
        if snapshot is None or not snapshot.items:
            raise RequirementGenerationContextRequired

        job_id = self._id_factory()
        event_id = self._id_factory()
        now = self._clock()
        payload_ref: dict[str, object] = {
            "context_version": command.context_version,
            "context_item_revisions": [
                {
                    "context_item_id": str(revision.context_item_id),
                    "updated_at": revision.updated_at.isoformat(),
                }
                for revision in snapshot.revision_vector
            ],
        }
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await unit_of_work.jobs.add(
                    NewJob(
                        id=job_id,
                        account_id=command.account_id,
                        project_id=command.project_id,
                        job_type=REQUIREMENT_GENERATION_JOB_TYPE,
                        status="queued",
                        payload_ref=payload_ref,
                        attempt_count=0,
                        max_attempts=REQUIREMENT_GENERATION_JOB_MAX_ATTEMPTS,
                        idempotency_key=None,
                        correlation_id=command.correlation_id,
                        available_at=now,
                    )
                )
                await unit_of_work.outbox.add(
                    NewOutboxEvent(
                        id=event_id,
                        account_id=command.account_id,
                        aggregate_type="project",
                        aggregate_id=command.project_id,
                        event_type=REQUIREMENT_GENERATION_EVENT_TYPE,
                        delivery_channel="job_queue",
                        payload={
                            "jobId": str(job_id),
                            "taskType": REQUIREMENT_GENERATION_JOB_TYPE,
                            "payloadVersion": REQUIREMENT_GENERATION_PAYLOAD_VERSION,
                        },
                        status="pending",
                        attempt_count=0,
                        available_at=now,
                    )
                )
                await unit_of_work.commit()
        except RequirementGenerationRepositoryError as error:
            self._event_logger.emit(
                "requirements.schedule_failed",
                level="ERROR",
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                correlation_id=str(command.correlation_id),
                context_version=command.context_version,
                reason_code="persistence_unavailable",
                status="failed",
            )
            raise RequirementGenerationSchedulingError from error

        self._event_logger.emit(
            "job.queued",
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            correlation_id=str(command.correlation_id),
            job_id=str(job_id),
            context_version=command.context_version,
            task_type=REQUIREMENT_GENERATION_JOB_TYPE,
            status="queued",
        )
        return RequirementGenerationScheduled(job_id=job_id, outbox_event_id=event_id)
