from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.scope.domain.scope_draft import NewScopeDraft, ScopeDraft


class ScopeDraftRepositoryError(Exception):
    """A declared Scope Draft persistence failure."""


class ScopeDraftNotFound(Exception):
    """No tenant-scoped Scope Draft exists."""


class ScopeDraftVersionConflict(Exception):
    """The Draft changed since the caller read it."""


class ScopeDraftHistorical(Exception):
    """The Draft is bound to an older Context Version."""


@dataclass(frozen=True, slots=True)
class ScopeDraftEditTarget:
    project_current_context_version: int
    draft: ScopeDraft | None


class ScopeDraftRepository(Protocol):
    async def get_by_id(
        self, *, account_id: UUID, project_id: UUID, draft_id: UUID
    ) -> ScopeDraft | None: ...
    async def get_by_context_version(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> ScopeDraft | None: ...
    async def get_current(
        self, *, account_id: UUID, project_id: UUID
    ) -> ScopeDraft | None: ...
    async def get_edit_target(
        self, *, account_id: UUID, project_id: UUID
    ) -> ScopeDraftEditTarget | None: ...
    async def add(self, draft: NewScopeDraft) -> ScopeDraft: ...
    async def update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        draft_id: UUID,
        expected_updated_at: datetime,
        content: dict[str, object],
        updated_by_type: str,
        updated_by: UUID | None,
    ) -> ScopeDraft: ...


class ScopeDraftUnitOfWork(Protocol):
    @property
    def repository(self) -> ScopeDraftRepository: ...
    async def __aenter__(self) -> ScopeDraftUnitOfWork: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...


class ScopeDraftUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeDraftUnitOfWork: ...
