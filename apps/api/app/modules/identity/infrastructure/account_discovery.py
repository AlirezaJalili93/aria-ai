from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.application.account_discovery import (
    AccountSelection,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import MembershipRole
from app.modules.identity.infrastructure.models import AccountMembershipModel


class SqlAlchemyAccountDiscovery:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(
        self, identity: AuthenticatedIdentity
    ) -> tuple[AccountSelection, ...]:
        user_id = identity.subject
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(
                        AccountMembershipModel.account_id,
                        AccountMembershipModel.role,
                    )
                    .where(
                        AccountMembershipModel.user_id == user_id,
                        AccountMembershipModel.status == "active",
                    )
                    .order_by(AccountMembershipModel.account_id)
                )
            ).all()
        return tuple(
            AccountSelection(id=account_id, role=cast(MembershipRole, role))
            for account_id, role in rows
            if role in {"owner", "admin", "member"}
        )
