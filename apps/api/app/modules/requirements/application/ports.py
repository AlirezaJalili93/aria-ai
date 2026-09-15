from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.requirements.domain.requirement import NewRequirement, Requirement


class RequirementRepositoryError(Exception):
    """A declared Requirement persistence failure."""


@dataclass(frozen=True, slots=True)
class RequirementProvenanceTarget:
    account_id: UUID
    project_id: UUID
    source_id: UUID
    source_version_id: UUID
    canonical_text_length: int | None


class RequirementRepository(Protocol):
    async def get_project_current_context_version(
        self, *, account_id: UUID, project_id: UUID
    ) -> int | None: ...

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> RequirementProvenanceTarget | None: ...

    async def add(self, requirement: NewRequirement) -> Requirement: ...


class RequirementUnitOfWork(Protocol):
    @property
    def repository(self) -> RequirementRepository: ...

    async def __aenter__(self) -> RequirementUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class RequirementUnitOfWorkFactory(Protocol):
    def __call__(self) -> RequirementUnitOfWork: ...
