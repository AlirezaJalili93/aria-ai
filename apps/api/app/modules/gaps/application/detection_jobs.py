from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID, uuid4

from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
    GapDetectionRepositoryError,
    GapDetectionSnapshotReader,
)
from aria_observability import StructuredEventLogger

from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

GAP_DETECTION_JOB_TYPE = "gap_detection"
GAP_DETECTION_EVENT_TYPE = "gap.detection_requested.v1"
GAP_DETECTION_PAYLOAD_VERSION = "1"
GAP_DETECTION_AUTOMATIC_QUEUE_RETRY = False
GAP_DETECTION_JOB_MAX_ATTEMPTS = 1


class GapDetectionSchedulingError(RuntimeError):
    """A safe internal AI-03 scheduling failure."""


class GapDetectionSyntheticFixtureRequired(GapDetectionSchedulingError):
    """The project is not explicitly approved for synthetic execution."""


class GapDetectionContextRequired(GapDetectionSchedulingError):
    """The exact usable Context revision is unavailable."""


class GapDetectionActiveJobConflict(GapDetectionSchedulingError):
    """Another active AI-03 Job targets the same Context version."""


class SyntheticGapDetectionAuthorizer(Protocol):
    def allows(self, *, account_id: UUID, project_id: UUID) -> bool: ...


class DenyAllSyntheticGapDetection:
    def allows(self, *, account_id: UUID, project_id: UUID) -> bool:
        del account_id, project_id
        return False


class ExplicitSyntheticGapDetectionProjects:
    def __init__(self, approved: frozenset[tuple[UUID, UUID]]) -> None:
        self._approved = approved

    def allows(self, *, account_id: UUID, project_id: UUID) -> bool:
        return (account_id, project_id) in self._approved


class GapDetectionJobUnitOfWork(Protocol):
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


class GapDetectionJobUnitOfWorkFactory(Protocol):
    def __call__(self) -> GapDetectionJobUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class ScheduleGapDetectionCommand:
    account_id: UUID
    project_id: UUID
    context_version: int
    correlation_id: UUID

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("context_version must be at least one")


@dataclass(frozen=True, slots=True)
class GapDetectionScheduled:
    job_id: UUID
    outbox_event_id: UUID


class ScheduleGapDetectionUseCase:
    """Internal-only scheduler for explicitly approved synthetic AI-03 fixtures."""

    def __init__(
        self,
        *,
        snapshot_reader: GapDetectionSnapshotReader,
        unit_of_work_factory: GapDetectionJobUnitOfWorkFactory,
        synthetic_authorizer: SyntheticGapDetectionAuthorizer,
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

    async def execute(self, command: ScheduleGapDetectionCommand) -> GapDetectionScheduled:
        if not self._synthetic_authorizer.allows(
            account_id=command.account_id, project_id=command.project_id
        ):
            raise GapDetectionSyntheticFixtureRequired
        snapshot = await self._snapshot_reader.resolve_exact(
            account_id=command.account_id,
            project_id=command.project_id,
            context_version=command.context_version,
            completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
        )
        if snapshot is None or not snapshot.context_items:
            raise GapDetectionContextRequired

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
                for revision in snapshot.context_item_revisions
            ],
            "requirement_revisions": [
                {
                    "requirement_id": str(revision.requirement_id),
                    "updated_at": revision.updated_at.isoformat(),
                }
                for revision in snapshot.requirement_revisions
            ],
            "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
            "critical_rule_pack_version": CRITICAL_GAP_RULE_PACK_VERSION,
        }
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await unit_of_work.jobs.add(
                    NewJob(
                        id=job_id,
                        account_id=command.account_id,
                        project_id=command.project_id,
                        job_type=GAP_DETECTION_JOB_TYPE,
                        status="queued",
                        payload_ref=payload_ref,
                        attempt_count=0,
                        max_attempts=GAP_DETECTION_JOB_MAX_ATTEMPTS,
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
                        event_type=GAP_DETECTION_EVENT_TYPE,
                        delivery_channel="job_queue",
                        payload={
                            "jobId": str(job_id),
                            "taskType": GAP_DETECTION_JOB_TYPE,
                            "payloadVersion": GAP_DETECTION_PAYLOAD_VERSION,
                        },
                        status="pending",
                        attempt_count=0,
                        available_at=now,
                    )
                )
                await unit_of_work.commit()
        except GapDetectionActiveJobConflict:
            raise
        except GapDetectionRepositoryError as error:
            self._event_logger.emit(
                "gap.schedule_failed",
                level="ERROR",
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                correlation_id=str(command.correlation_id),
                context_version=command.context_version,
                reason_code="persistence_unavailable",
                status="failed",
            )
            raise GapDetectionSchedulingError from error

        self._event_logger.emit(
            "job.queued",
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            correlation_id=str(command.correlation_id),
            job_id=str(job_id),
            context_version=command.context_version,
            task_type=GAP_DETECTION_JOB_TYPE,
            status="queued",
        )
        return GapDetectionScheduled(job_id=job_id, outbox_event_id=event_id)
