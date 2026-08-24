from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.membership import MembershipRole, MembershipStatus


@dataclass(frozen=True, slots=True)
class ResolvedMembership:
    membership_id: UUID
    account_id: UUID
    user_id: UUID
    role: MembershipRole
    status: MembershipStatus


class AccountBootstrapRepository(Protocol):
    async def resolve_memberships(self, user_id: UUID) -> tuple[ResolvedMembership, ...]: ...

    async def create_profile_if_absent(self, user_id: UUID) -> bool:
        """Insert the projection through the Profile PK conflict gate."""
        ...

    async def add_account(self, account_id: UUID) -> None: ...

    async def add_owner_membership(
        self,
        *,
        membership_id: UUID,
        account_id: UUID,
        user_id: UUID,
    ) -> None: ...


class AccountBootstrapUnitOfWork(Protocol):
    @property
    def repository(self) -> AccountBootstrapRepository: ...

    async def __aenter__(self) -> AccountBootstrapUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class AccountBootstrapUnitOfWorkFactory(Protocol):
    def __call__(self) -> AccountBootstrapUnitOfWork: ...
