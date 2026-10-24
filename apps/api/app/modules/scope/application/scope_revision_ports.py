from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.scope.domain.readiness import ScopeReadinessGap
from app.modules.scope.domain.scope_draft import ScopeDraft
from app.modules.scope.domain.scope_version import NewScopeVersion, ScopeVersion


class ScopeRevisionRepositoryError(Exception):
    """A declared Scope Revision persistence failure."""


@dataclass(frozen=True, slots=True)
class ScopeRevisionReservation:
    acquired: bool
    request_hash: str
    scope_version_id: UUID
    response: ScopeVersion | None


@dataclass(frozen=True, slots=True)
class ScopeRevisionTarget:
    project_current_context_version: int
    target: ScopeVersion
    latest_scope_version_id: UUID
    change_request_scope_version_id: UUID
    change_request_consumed: bool
    draft: ScopeDraft | None
    gaps: tuple[ScopeReadinessGap, ...]


class ScopeRevisionRepository(Protocol):
    async def lock_visible_target(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> ScopeVersion | None: ...

    async def reserve_revision(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        target_version_no: int,
        idempotency_key: str,
        request_hash: str,
        scope_version_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> ScopeRevisionReservation: ...

    async def get_revision_target(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        target_version_no: int,
        change_request_id: UUID,
    ) -> ScopeRevisionTarget | None: ...

    async def add_revision(self, version: NewScopeVersion) -> ScopeVersion: ...

    async def supersede_target(self, *, target_scope_version_id: UUID) -> None: ...

    async def complete_revision_reservation(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        target_version_no: int,
        idempotency_key: str,
        request_hash: str,
        version: ScopeVersion,
    ) -> None: ...


class ScopeRevisionUnitOfWork(Protocol):
    @property
    def repository(self) -> ScopeRevisionRepository: ...

    async def __aenter__(self) -> ScopeRevisionUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ScopeRevisionUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeRevisionUnitOfWork: ...
