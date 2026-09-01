from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import MembershipRole


@dataclass(frozen=True, slots=True)
class AccountSelection:
    id: UUID
    role: MembershipRole


class AccountDiscovery(Protocol):
    async def execute(
        self, identity: AuthenticatedIdentity
    ) -> tuple[AccountSelection, ...]: ...


class AccountDiscoveryRepository(Protocol):
    async def list_active_for_user(self, user_id: UUID) -> tuple[AccountSelection, ...]: ...


class DiscoverAccountsUseCase:
    def __init__(self, repository: AccountDiscoveryRepository) -> None:
        self._repository = repository

    async def execute(
        self, identity: AuthenticatedIdentity
    ) -> tuple[AccountSelection, ...]:
        return await self._repository.list_active_for_user(identity.subject)
