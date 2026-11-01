from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.sharing.domain.scope_approval import NewScopeApproval, ScopeApproval


class ScopeApprovalRepositoryError(Exception):
    """A declared public Scope Approval persistence failure."""


@dataclass(frozen=True, slots=True)
class ScopeApprovalTarget:
    account_id: UUID
    project_id: UUID
    share_link_id: UUID
    scope_version_id: UUID
    version_no: int
    version_hash: str
    scope_status: str


class ScopeApprovalRepository(Protocol):
    async def resolve_target_for_update(
        self, *, token_hash: bytes, now: datetime
    ) -> ScopeApprovalTarget | None: ...

    async def approval_for_scope_version(self, scope_version_id: UUID) -> ScopeApproval | None: ...

    async def add(self, approval: NewScopeApproval) -> ScopeApproval: ...

    async def mark_scope_version_approved(self, scope_version_id: UUID) -> None: ...


class ScopeApprovalUnitOfWork(Protocol):
    @property
    def repository(self) -> ScopeApprovalRepository: ...

    async def __aenter__(self) -> ScopeApprovalUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ScopeApprovalUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeApprovalUnitOfWork: ...
