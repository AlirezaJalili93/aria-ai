from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.db.models import Base
from app.shared.idempotency import (
    IdempotencyRepositoryError,
    IdempotencyReservation,
)


class IdempotencyRecordModel(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "actor_id",
            "route_key",
            "idempotency_key",
            name="uq_idempotency_scope_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.user_id"), nullable=False)
    route_key: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SqlAlchemyIdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self,
        *,
        record_id: UUID,
        account_id: UUID,
        actor_id: UUID,
        route_key: str,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> IdempotencyReservation:
        scope = (
            IdempotencyRecordModel.account_id == account_id,
            IdempotencyRecordModel.actor_id == actor_id,
            IdempotencyRecordModel.route_key == route_key,
            IdempotencyRecordModel.idempotency_key == idempotency_key,
        )
        await self._session.execute(
            delete(IdempotencyRecordModel).where(
                *scope,
                IdempotencyRecordModel.expires_at <= now,
            )
        )
        inserted = await self._session.scalar(
            insert(IdempotencyRecordModel)
            .values(
                id=record_id,
                account_id=account_id,
                actor_id=actor_id,
                route_key=route_key,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "actor_id", "route_key", "idempotency_key"]
            )
            .returning(IdempotencyRecordModel.id)
        )
        if inserted is not None:
            return IdempotencyReservation(True, request_hash, None, None)

        existing = await self._session.scalar(select(IdempotencyRecordModel).where(*scope))
        if existing is None:
            raise IdempotencyRepositoryError
        return IdempotencyReservation(
            False,
            existing.request_hash,
            existing.response_status,
            existing.response_ref,
        )

    async def complete(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        route_key: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_ref: dict[str, object],
    ) -> None:
        completed = await self._session.scalar(
            update(IdempotencyRecordModel)
            .where(
                IdempotencyRecordModel.account_id == account_id,
                IdempotencyRecordModel.actor_id == actor_id,
                IdempotencyRecordModel.route_key == route_key,
                IdempotencyRecordModel.idempotency_key == idempotency_key,
                IdempotencyRecordModel.request_hash == request_hash,
            )
            .values(response_status=response_status, response_ref=response_ref)
            .returning(IdempotencyRecordModel.id)
        )
        if completed is None:
            raise IdempotencyRepositoryError
