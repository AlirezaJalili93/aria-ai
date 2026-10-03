from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol
from uuid import UUID

from app.modules.context.domain.context_item import (
    ContextItem,
    ContextItemStatus,
    ContextItemType,
    NewContextItem,
)


class ContextItemRepositoryError(Exception):
    """A declared Context Item persistence failure."""


@dataclass(frozen=True, slots=True)
class ProvenanceTarget:
    account_id: UUID
    project_id: UUID
    source_id: UUID
    source_version_id: UUID
    canonical_text_length: int | None


@dataclass(frozen=True, slots=True)
class CurrentContextItems:
    context_version: int
    items: tuple[ContextItem, ...]


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

    async def list_current(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        item_type: ContextItemType | None,
        status: ContextItemStatus | None,
        source_id: UUID | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> CurrentContextItems | None: ...

    async def get_current_for_update(
        self, *, account_id: UUID, project_id: UUID, item_id: UUID
    ) -> ContextItem | None: ...

    async def update_proposed(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        item_id: UUID,
        expected_updated_at: datetime,
        content: str,
        status: Literal["proposed", "confirmed", "rejected"],
    ) -> ContextItem | None: ...


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
