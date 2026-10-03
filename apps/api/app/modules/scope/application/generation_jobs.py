from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID, uuid4

from aria_backend_application.scope_generation import (
    ScopeDraftAlreadyExistsError,
)
from aria_backend_application.scope_generation import (
    ScopeGenerationRequirementsRequiredError as ScopeGenerationRequirementsRequired,
)
from aria_backend_application.scope_generation import (
    ScopeInputRevision as ScopeGenerationInputRevision,
)
from aria_observability import StructuredEventLogger

from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

SCOPE_GENERATION_JOB_TYPE = "scope_generation"
SCOPE_GENERATION_EVENT_TYPE = "scope.generation_requested.v1"
SCOPE_GENERATION_PAYLOAD_VERSION = "1"
SCOPE_GENERATION_AUTOMATIC_QUEUE_RETRY = False
# The existing Jobs schema requires max_attempts >= 1. This is not a retry policy.
SCOPE_GENERATION_JOB_MAX_ATTEMPTS = 1


class ScopeGenerationSchedulingError(RuntimeError):
    """Safe internal AI-05 scheduling failure."""


class ScopeGenerationSyntheticFixtureRequired(ScopeGenerationSchedulingError):
    """The project is not explicitly approved for synthetic execution."""


class ScopeGenerationContextRequired(ScopeGenerationSchedulingError):
    """An exact usable Context Version is required."""


class ScopeGenerationBlocked(ScopeGenerationSchedulingError):
    """K02 reports an open Critical Gap."""


class ScopeGenerationActiveJobConflict(ScopeGenerationSchedulingError):
    """A queued or running AI-05 Job already targets this Context Version."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeGenerationPreflight:
    context_item_revisions: tuple[ScopeGenerationInputRevision, ...]
    requirement_revisions: tuple[ScopeGenerationInputRevision, ...]
    gap_revisions: tuple[ScopeGenerationInputRevision, ...]
    ready_for_share: bool
    draft_exists: bool

    def __post_init__(self) -> None:
        for revisions in (
            self.context_item_revisions,
            self.requirement_revisions,
            self.gap_revisions,
        ):
            if revisions != tuple(sorted(revisions, key=lambda item: item.id.int)):
                raise ValueError("Input revisions must be sorted by ID")
            if len({item.id for item in revisions}) != len(revisions):
                raise ValueError("Input revision IDs must be unique")


class ScopeGenerationPreflightReader(Protocol):
    async def resolve_exact(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> ScopeGenerationPreflight | None: ...


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


class ScopeGenerationJobUnitOfWork(Protocol):
    async def verify_draft_absent(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> None: ...

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


class ScopeGenerationJobUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeGenerationJobUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class ScheduleScopeGenerationCommand:
    account_id: UUID
    project_id: UUID
    context_version: int
    correlation_id: UUID

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("context_version must be at least one")


@dataclass(frozen=True, slots=True)
class ScopeGenerationScheduled:
    job_id: UUID
    outbox_event_id: UUID


def _revision_payload(values: tuple[ScopeGenerationInputRevision, ...]) -> list[dict[str, str]]:
    return [{"id": str(value.id), "updated_at": value.updated_at.isoformat()} for value in values]


class ScheduleScopeGenerationUseCase:
    """Internal-only scheduler for explicitly approved synthetic AI-05 fixtures."""

    def __init__(
        self,
        *,
        preflight_reader: ScopeGenerationPreflightReader,
        unit_of_work_factory: ScopeGenerationJobUnitOfWorkFactory,
        synthetic_authorizer: SyntheticScopeAuthorizer,
        event_logger: StructuredEventLogger,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._preflight_reader = preflight_reader
        self._unit_of_work_factory = unit_of_work_factory
        self._synthetic_authorizer = synthetic_authorizer
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(self, command: ScheduleScopeGenerationCommand) -> ScopeGenerationScheduled:
        if not self._synthetic_authorizer.allows(
            account_id=command.account_id, project_id=command.project_id
        ):
            raise ScopeGenerationSyntheticFixtureRequired
        snapshot = await self._preflight_reader.resolve_exact(
            account_id=command.account_id,
            project_id=command.project_id,
            context_version=command.context_version,
        )
        if snapshot is None or not snapshot.context_item_revisions:
            raise ScopeGenerationContextRequired
        if not snapshot.requirement_revisions:
            raise ScopeGenerationRequirementsRequired
        if not snapshot.ready_for_share:
            raise ScopeGenerationBlocked
        if snapshot.draft_exists:
            raise ScopeDraftAlreadyExistsError

        job_id, event_id, now = self._id_factory(), self._id_factory(), self._clock()
        payload_ref: dict[str, object] = {
            "context_version": command.context_version,
            "context_item_revisions": _revision_payload(snapshot.context_item_revisions),
            "requirement_revisions": _revision_payload(snapshot.requirement_revisions),
            "gap_revisions": _revision_payload(snapshot.gap_revisions),
        }
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.verify_draft_absent(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            await unit_of_work.jobs.add(
                NewJob(
                    id=job_id,
                    account_id=command.account_id,
                    project_id=command.project_id,
                    job_type=SCOPE_GENERATION_JOB_TYPE,
                    status="queued",
                    payload_ref=payload_ref,
                    attempt_count=0,
                    max_attempts=SCOPE_GENERATION_JOB_MAX_ATTEMPTS,
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
                    event_type=SCOPE_GENERATION_EVENT_TYPE,
                    delivery_channel="job_queue",
                    payload={
                        "jobId": str(job_id),
                        "taskType": SCOPE_GENERATION_JOB_TYPE,
                        "payloadVersion": SCOPE_GENERATION_PAYLOAD_VERSION,
                    },
                    status="pending",
                    attempt_count=0,
                    available_at=now,
                )
            )
            await unit_of_work.commit()
        self._event_logger.emit(
            "job.queued",
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            correlation_id=str(command.correlation_id),
            job_id=str(job_id),
            context_version=command.context_version,
            task_type=SCOPE_GENERATION_JOB_TYPE,
            status="queued",
        )
        return ScopeGenerationScheduled(job_id=job_id, outbox_event_id=event_id)
