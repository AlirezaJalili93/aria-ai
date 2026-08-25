from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.identity.application.membership_resolution import MembershipResolver
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import MembershipRole, MembershipStatus


@dataclass(frozen=True, slots=True)
class TenantContext:
    subject_id: UUID
    account_id: UUID
    membership_id: UUID
    role: MembershipRole
    membership_status: MembershipStatus


class TenantContextResolver(Protocol):
    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> TenantContext: ...


class ResolveTenantContextUseCase:
    def __init__(self, membership_resolver: MembershipResolver) -> None:
        self._membership_resolver = membership_resolver

    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> TenantContext:
        active_membership = await self._membership_resolver.execute(identity, account_id)
        membership = active_membership.membership
        return TenantContext(
            subject_id=active_membership.subject,
            account_id=membership.account_id,
            membership_id=membership.membership_id,
            role=membership.role,
            membership_status=membership.status,
        )
