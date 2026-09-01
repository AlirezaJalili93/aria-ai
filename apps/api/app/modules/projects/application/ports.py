from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.projects.domain.project import NewProject, Project, ProjectStatus


class ProjectRepositoryError(Exception):
    """A declared Project persistence failure."""


@dataclass(frozen=True, slots=True)
class ProjectCreateReservation:
    acquired: bool
    payload_hash: str
    project_id: UUID
    response_snapshot: Project | None


class ProjectRepository(Protocol):
    async def reserve_create(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        idempotency_key: str,
        payload_hash: str,
        project_id: UUID,
    ) -> ProjectCreateReservation: ...

    async def complete_create_reservation(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        idempotency_key: str,
        project: Project,
    ) -> None: ...

    async def add(self, project: NewProject) -> Project: ...

    async def get(self, *, account_id: UUID, project_id: UUID) -> Project | None: ...

    async def get_including_deleted(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> Project | None: ...

    async def list_by_account(
        self,
        *,
        account_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Project, ...]: ...

    async def update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        title: str | None = None,
        status: ProjectStatus | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Project | None: ...

    async def soft_delete(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> Project | None: ...


class ProjectUnitOfWork(Protocol):
    @property
    def repository(self) -> ProjectRepository: ...

    async def __aenter__(self) -> ProjectUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ProjectUnitOfWorkFactory(Protocol):
    def __call__(self) -> ProjectUnitOfWork: ...
