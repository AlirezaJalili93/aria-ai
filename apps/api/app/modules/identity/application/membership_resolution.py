from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, cast
from uuid import UUID

from app.modules.identity.application.membership_ports import (
    MembershipProjectionInvariantError,
    MembershipResolutionRepository,
    ResolvedMembership,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import ACTIVE_MEMBERSHIP_STATUS

MembershipDenialReason = Literal["not_found", "invited", "suspended"]


class ActiveMembershipRequired(Exception):
    """The identity has no active Membership for the requested Account."""

    def __init__(self, *, reason_code: MembershipDenialReason) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ActiveMembershipContext:
    subject: UUID
    membership: ResolvedMembership

    @property
    def account_id(self) -> UUID:
        return self.membership.account_id


class MembershipResolver(Protocol):
    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> ActiveMembershipContext: ...


class ResolveActiveMembershipUseCase:
    def __init__(self, repository: MembershipResolutionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> ActiveMembershipContext:
        membership = await self._repository.resolve_membership(
            user_id=identity.subject,
            account_id=account_id,
        )
        if membership is None:
            raise ActiveMembershipRequired(reason_code="not_found")
        if membership.status != ACTIVE_MEMBERSHIP_STATUS:
            raise ActiveMembershipRequired(
                reason_code=cast(MembershipDenialReason, membership.status)
            )
        if membership.user_id != identity.subject or membership.account_id != account_id:
            raise MembershipProjectionInvariantError
        return ActiveMembershipContext(subject=identity.subject, membership=membership)
