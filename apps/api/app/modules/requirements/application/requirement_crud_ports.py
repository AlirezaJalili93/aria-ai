from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.requirements.domain.requirement import (
    NewRequirement,
    Requirement,
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
)
from app.shared.idempotency import IdempotencyRepository


class RequirementCrudRepositoryError(Exception):
    """A declared Requirement CRUD persistence failure."""


class RequirementCrudRepository(Protocol):
    async def get_project_current_context_version(
        self, *, account_id: UUID, project_id: UUID
    ) -> int | None: ...

    async def add(self, requirement: NewRequirement) -> Requirement: ...

    async def get_by_id(
        self, *, account_id: UUID, project_id: UUID, requirement_id: UUID
    ) -> Requirement | None: ...

    async def list_by_project(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        category: RequirementCategory | None,
        status: RequirementStatus | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Requirement, ...] | None: ...

    async def get_for_update(
        self, *, account_id: UUID, project_id: UUID, requirement_id: UUID
    ) -> Requirement | None: ...

    async def update_mutable(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        expected_updated_at: datetime,
        title: str,
        description: str,
        priority: RequirementPriority,
        acceptance_note: str | None,
        status: RequirementStatus,
    ) -> Requirement | None: ...


class RequirementCrudUnitOfWork(Protocol):
    @property
    def repository(self) -> RequirementCrudRepository: ...

    @property
    def idempotency(self) -> IdempotencyRepository: ...

    async def __aenter__(self) -> RequirementCrudUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class RequirementCrudUnitOfWorkFactory(Protocol):
    def __call__(self) -> RequirementCrudUnitOfWork: ...
