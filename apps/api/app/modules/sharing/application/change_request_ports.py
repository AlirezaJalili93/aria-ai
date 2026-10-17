from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.sharing.domain.scope_change_request import (
    NewScopeChangeRequest,
    ScopeChangeRequest,
)


class ScopeChangeRequestRepositoryError(Exception):
    """A declared public Scope Change Request persistence failure."""


@dataclass(frozen=True, slots=True)
class ScopeChangeRequestTarget:
    account_id: UUID
    project_id: UUID
    share_link_id: UUID
    scope_version_id: UUID
    version_no: int
    version_hash: str
    scope_status: str


class ScopeChangeRequestRepository(Protocol):
    async def resolve_target_for_update(
        self, *, token_hash: bytes, now: datetime
    ) -> ScopeChangeRequestTarget | None: ...

    async def change_request_for_scope_version(
        self, scope_version_id: UUID
    ) -> ScopeChangeRequest | None: ...

    async def add(self, change_request: NewScopeChangeRequest) -> ScopeChangeRequest: ...

    async def mark_scope_version_changes_requested(self, scope_version_id: UUID) -> None: ...


class ScopeChangeRequestUnitOfWork(Protocol):
    @property
    def repository(self) -> ScopeChangeRequestRepository: ...

    async def __aenter__(self) -> ScopeChangeRequestUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ScopeChangeRequestUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeChangeRequestUnitOfWork: ...
