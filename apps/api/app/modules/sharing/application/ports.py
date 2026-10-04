from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

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
    snapshot_data: dict[str, object]


class ScopeShareLinkRepository(Protocol):
    @staticmethod
    def create_route_key(project_id: UUID) -> str: ...

    @staticmethod
    def revoke_route_key(project_id: UUID) -> str: ...

    async def scope_version_id(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> UUID | None: ...

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
