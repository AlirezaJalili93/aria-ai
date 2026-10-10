from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol
from uuid import UUID

from app.modules.scope.domain.scope_version import ScopeVersionStatus
from app.modules.sharing.domain.scope_share_link import NewScopeShareLink, ScopeShareLink
from app.shared.idempotency import IdempotencyRepository


class ScopeShareLinkRepositoryError(Exception):
    """A declared Scope Share Link persistence failure."""


@dataclass(frozen=True, slots=True)
class IssuedScopeShareToken:
    public_token: str
    token_hash: bytes


class ScopeShareTokenIssuer(Protocol):
    def issue(self) -> IssuedScopeShareToken: ...


class ScopeShareTokenHasher(Protocol):
    def hash_public_token(self, public_token: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class ResolvedPublicScope:
    share_link_id: UUID
    scope_version_id: UUID
    version_no: int
    decision_status: ScopeVersionStatus
    snapshot_data: dict[str, object]


@dataclass(frozen=True, slots=True)
class ScopeShareCreateTarget:
    id: UUID
    status: ScopeVersionStatus


@dataclass(frozen=True, slots=True)
class ScopeShareLinkProjection:
    link: ScopeShareLink
    scope_version_no: int


@dataclass(frozen=True, slots=True)
class ScopeDecisionProjection:
    decision_type: Literal["none", "approval", "change_request"]
    scope_version_no: int
    decision_id: UUID | None = None
    guest_name: str | None = None
    comment: str | None = None
    decided_at: datetime | None = None


class ScopeShareLinkRepository(Protocol):
    @staticmethod
    def create_route_key(project_id: UUID) -> str: ...

    @staticmethod
    def revoke_route_key(project_id: UUID) -> str: ...

    async def scope_version_id(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> UUID | None: ...

    async def lock_scope_version_for_share_create(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> ScopeShareCreateTarget | None: ...

    async def scope_version_exists(
        self, *, account_id: UUID, project_id: UUID, scope_version_id: UUID
    ) -> bool: ...

    async def add(self, link: NewScopeShareLink) -> ScopeShareLink: ...

    async def get_for_update(
        self, *, account_id: UUID, project_id: UUID, share_link_id: UUID
    ) -> ScopeShareLink | None: ...

    async def set_revoked(self, link: ScopeShareLink) -> ScopeShareLink: ...

    async def resolve_public(
        self, *, token_hash: bytes, now: datetime
    ) -> ResolvedPublicScope | None: ...

    async def list_for_scope_version(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        scope_version_id: UUID,
        actor_id: UUID | None,
    ) -> tuple[ScopeShareLinkProjection, ...]: ...

    async def decision_for_scope_version(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        scope_version_id: UUID,
    ) -> ScopeDecisionProjection | None: ...


class ScopeShareLinkUnitOfWork(Protocol):
    @property
    def repository(self) -> ScopeShareLinkRepository: ...
    @property
    def idempotency(self) -> IdempotencyRepository: ...
    async def __aenter__(self) -> ScopeShareLinkUnitOfWork: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...


class ScopeShareLinkUnitOfWorkFactory(Protocol):
    def __call__(self) -> ScopeShareLinkUnitOfWork: ...
