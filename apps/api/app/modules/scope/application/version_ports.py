from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.scope.domain.readiness import ScopeReadinessGap
from app.modules.scope.domain.scope_draft import ScopeDraft
from app.modules.scope.domain.scope_version import NewScopeVersion, ScopeVersion


class ScopeVersionRepositoryError(Exception):
    """A declared Scope Version persistence failure."""


@dataclass(frozen=True, slots=True)
class ScopeVersionCreateReservation:
    acquired: bool
    request_hash: str
    scope_version_id: UUID
    response: ScopeVersion | None


@dataclass(frozen=True, slots=True)
class ScopeVersionFreezeTarget:
    project_current_context_version: int
    draft: ScopeDraft | None
    gaps: tuple[ScopeReadinessGap, ...]
    latest_snapshot_hash: str | None
    next_version_no: int


class ScopeVersionRepository(Protocol):
    async def reserve_create(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        scope_version_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> ScopeVersionCreateReservation: ...

    async def get_freeze_target(
        self, *, account_id: UUID, project_id: UUID
    ) -> ScopeVersionFreezeTarget | None: ...

    async def add(self, version: NewScopeVersion) -> ScopeVersion: ...

    async def complete_create_reservation(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        version: ScopeVersion,
    ) -> None: ...

    async def get(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> ScopeVersion | None: ...

    async def list(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        limit: int,
        before_version_no: int | None,
    ) -> tuple[ScopeVersion, ...] | None: ...


class ScopeVersionUnitOfWork(Protocol):
    @property
    def repository(self) -> ScopeVersionRepository: ...
    async def __aenter__(self) -> ScopeVersionUnitOfWork: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...


class ScopeVersionUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeVersionUnitOfWork: ...
