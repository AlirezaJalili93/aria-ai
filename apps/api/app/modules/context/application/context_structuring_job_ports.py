from __future__ import annotations

from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.projects.application.ports import ProjectRepository
from app.shared.idempotency import IdempotencyRepository


class ContextStructuringJobRepositoryError(Exception):
    """A declared Context Structuring scheduling persistence failure."""


class ContextStructuringActiveJobConflict(ContextStructuringJobRepositoryError):
    """The database rejected a second active AI-01 Job for one Project."""


class ContextStructuringReadinessRepository(Protocol):
    async def has_ready_source(self, *, account_id: UUID, project_id: UUID) -> bool: ...


class SyntheticContextStructuringAuthorizer(Protocol):
    """Fail-closed boundary for the controlled synthetic-only runtime."""

    def allows(self, *, account_id: UUID, project_id: UUID) -> bool: ...


class ContextStructuringJobUnitOfWork(Protocol):
    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def readiness(self) -> ContextStructuringReadinessRepository: ...

    @property
    def jobs(self) -> JobRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    @property
    def idempotency(self) -> IdempotencyRepository: ...

    async def __aenter__(self) -> ContextStructuringJobUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ContextStructuringJobUnitOfWorkFactory(Protocol):
    def __call__(self) -> ContextStructuringJobUnitOfWork: ...
