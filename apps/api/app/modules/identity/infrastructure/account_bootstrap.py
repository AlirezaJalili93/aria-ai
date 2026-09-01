from __future__ import annotations

from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.application.account_bootstrap import (
    AccountBootstrapInfrastructureError,
)
from app.modules.identity.application.bootstrap_ports import (
    AccountBootstrapUnitOfWork,
    ResolvedMembership,
)
from app.modules.identity.application.membership_ports import MembershipProjectionInvariantError
from app.modules.identity.domain.membership import MembershipRole, MembershipStatus
from app.modules.identity.infrastructure.models import (
    AccountMembershipModel,
    AccountModel,
    ProfileModel,
)


class SqlAlchemyAccountBootstrapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_memberships(self, user_id: UUID) -> tuple[ResolvedMembership, ...]:
        statement = (
            select(AccountMembershipModel)
            .where(AccountMembershipModel.user_id == user_id)
            .order_by(AccountMembershipModel.joined_at, AccountMembershipModel.id)
        )
        rows = (await self._session.scalars(statement)).all()
        return tuple(_resolved_membership(row) for row in rows)

    async def create_profile_if_absent(self, user_id: UUID) -> bool:
        statement = (
            insert(ProfileModel)
            .values(user_id=user_id)
            .on_conflict_do_nothing(index_elements=[ProfileModel.user_id])
            .returning(ProfileModel.user_id)
        )
        return (await self._session.scalar(statement)) is not None

    async def add_account(self, account_id: UUID) -> None:
        self._session.add(AccountModel(id=account_id))
        # The models intentionally expose no ORM relationship. Flush the parent explicitly so
        # PostgreSQL always observes the Account FK target before Membership is inserted.
        await self._session.flush()

    async def add_owner_membership(
        self,
        *,
        membership_id: UUID,
        account_id: UUID,
        user_id: UUID,
    ) -> None:
        self._session.add(
            AccountMembershipModel(
                id=membership_id,
                account_id=account_id,
                user_id=user_id,
                role="owner",
                status="active",
            )
        )


class SqlAlchemyAccountBootstrapUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyAccountBootstrapRepository | None = None
        self._committed = False

    @property
    def repository(self) -> SqlAlchemyAccountBootstrapRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyAccountBootstrapUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyAccountBootstrapRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, traceback
        if self._session is None:
            return
        if not self._committed:
            await self._session.rollback()
        await self._session.close()
        if isinstance(exc, SQLAlchemyError):
            raise AccountBootstrapInfrastructureError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyAccountBootstrapUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> AccountBootstrapUnitOfWork:
        return SqlAlchemyAccountBootstrapUnitOfWork(self._session_factory)


def _resolved_membership(row: AccountMembershipModel) -> ResolvedMembership:
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
