from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.membership import MembershipRole, MembershipStatus


class MembershipProjectionInvariantError(Exception):
    """Persisted Membership data violates the approved domain vocabulary."""


@dataclass(frozen=True, slots=True)
class ResolvedMembership:
    membership_id: UUID
    account_id: UUID
    user_id: UUID
    role: MembershipRole
    status: MembershipStatus


class MembershipResolutionRepository(Protocol):
    async def resolve_membership(
        self,
        *,
        user_id: UUID,
        account_id: UUID,
    ) -> ResolvedMembership | None: ...
