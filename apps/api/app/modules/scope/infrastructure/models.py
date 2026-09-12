from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class ScopeDraftModel(Base):
    __tablename__ = "scope_drafts"
    __table_args__ = (
        CheckConstraint("context_version >= 1", name="scope_draft_context_version"),
        CheckConstraint("jsonb_typeof(content) = 'object'", name="scope_draft_content_object"),
        CheckConstraint(
            "updated_by_type IN ('user','ai','system')", name="scope_draft_updated_by_type"
        ),
        CheckConstraint(
            "updated_by_type <> 'user' OR updated_by IS NOT NULL",
            name="scope_draft_user_updated_by",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_drafts_project_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id", "context_version", name="uq_scope_drafts_project_context_version"
        ),
        Index(
            "ix_scope_drafts_account_project_context", "account_id", "project_id", "context_version"
        ),
        Index("ix_scope_drafts_account_updated_at", "account_id", text("updated_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    updated_by_type: Mapped[str] = mapped_column(nullable=False)
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
