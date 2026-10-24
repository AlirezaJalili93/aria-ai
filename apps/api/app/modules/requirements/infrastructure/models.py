from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class RequirementModel(Base):
    __tablename__ = "requirements"
    __table_args__ = (
        CheckConstraint("context_version >= 1", name="requirement_context_version"),
        CheckConstraint(
            "category IN ('functional','content','visual','technical','constraint','business')",
            name="requirement_category",
        ),
        CheckConstraint("priority IN ('must','should','could')", name="requirement_priority"),
        CheckConstraint(
            "status IN ('draft','confirmed','superseded','removed')",
            name="requirement_status",
        ),
        CheckConstraint("created_by_type IN ('ai','user')", name="requirement_created_by_type"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="requirement_confidence",
        ),
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name="requirement_source_refs_array"
        ),
        CheckConstraint(
            "created_by_type <> 'user' OR created_by IS NOT NULL",
            name="requirement_user_creator",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_requirements_project_id_account_id_projects",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "account_id",
            "project_id",
            name="uq_requirements_id_account_project",
        ),
        Index(
            "ix_requirements_account_project_status_category",
            "account_id",
            "project_id",
            "status",
            "category",
        ),
        Index(
            "ix_requirements_account_project_generation_job",
            "account_id",
            "project_id",
            "generation_job_id",
        ),
        Index("ix_requirements_created_by", "created_by"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    source_refs: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_unsupported: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    duplicate_group_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=True
    )
    acceptance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_type: Mapped[str] = mapped_column(String(10), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
