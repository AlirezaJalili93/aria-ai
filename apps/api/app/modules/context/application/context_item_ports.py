from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.context.domain.context_item import ContextItem, NewContextItem


class ContextItemRepositoryError(Exception):
    """A declared Context Item persistence failure."""


@dataclass(frozen=True, slots=True)
class ProvenanceTarget:
    account_id: UUID
    project_id: UUID
    source_id: UUID
    source_version_id: UUID
    canonical_text_length: int | None


class ContextItemRepository(Protocol):
    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> ProvenanceTarget | None: ...

    async def add(self, item: NewContextItem) -> ContextItem: ...


class ContextItemUnitOfWork(Protocol):
    @property
    def repository(self) -> ContextItemRepository: ...

    async def __aenter__(self) -> ContextItemUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ContextItemUnitOfWorkFactory(Protocol):
    def __call__(self) -> ContextItemUnitOfWork: ...
