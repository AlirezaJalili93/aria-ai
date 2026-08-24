from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','suspended','closed')",
            name="account_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False, server_default="free")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProfileModel(Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, server_default="fa-IR")
    profile_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AccountMembershipModel(Base):
    __tablename__ = "account_memberships"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id"),
        CheckConstraint("role IN ('owner','admin','member')", name="membership_role"),
        CheckConstraint(
            "status IN ('active','invited','suspended')",
            name="membership_status",
        ),
        Index("ix_account_memberships_user_id_status", "user_id", "status"),
        Index("ix_account_memberships_account_id_status", "account_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.user_id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
