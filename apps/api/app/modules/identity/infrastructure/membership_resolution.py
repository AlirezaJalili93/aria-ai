from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.application.membership_ports import (
    MembershipProjectionInvariantError,
    ResolvedMembership,
)
from app.modules.identity.application.membership_resolution import (
    ActiveMembershipContext,
    ResolveActiveMembershipUseCase,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import MembershipRole, MembershipStatus
from app.modules.identity.infrastructure.models import AccountMembershipModel


class SqlAlchemyMembershipResolutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_membership(
        self,
        *,
        user_id: UUID,
        account_id: UUID,
    ) -> ResolvedMembership | None:
        statement = select(AccountMembershipModel).where(
            AccountMembershipModel.user_id == user_id,
            AccountMembershipModel.account_id == account_id,
        )
        row = await self._session.scalar(statement)
        if row is None:
            return None
        if row.role not in {"owner", "admin", "member"} or row.status not in {
            "active",
            "invited",
            "suspended",
        }:
            raise MembershipProjectionInvariantError
        return ResolvedMembership(
            membership_id=row.id,
            account_id=row.account_id,
            user_id=row.user_id,
            role=cast(MembershipRole, row.role),
            status=cast(MembershipStatus, row.status),
        )


class SqlAlchemyMembershipResolver:
    """Resolve Membership in a short, request-scoped read transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> ActiveMembershipContext:
        async with self._session_factory() as session:
            return await ResolveActiveMembershipUseCase(
                SqlAlchemyMembershipResolutionRepository(session)
            ).execute(identity, account_id)
