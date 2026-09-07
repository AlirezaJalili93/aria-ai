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
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class GapModel(Base):
    __tablename__ = "gaps"
    __table_args__ = (
        CheckConstraint("context_version >= 1", name="gap_context_version"),
        CheckConstraint(
            "gap_type IN "
            "('missing_information','ambiguity','conflict','decision_required',"
            "'unsupported_assumption','scope_risk')",
            name="gap_type",
        ),
        CheckConstraint(
            "severity IN ('critical','high','medium','low')", name="gap_severity"
        ),
        CheckConstraint(
            "status IN ('open','resolved','dismissed')", name="gap_status"
        ),
        CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name="gap_source_refs_array"
        ),
        CheckConstraint(
            "resolved_at IS NULL OR status = 'resolved'", name="gap_resolved_at_status"
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_gaps_project_id_account_id_projects",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_gaps_account_project_status_severity",
            "account_id",
            "project_id",
            "status",
            "severity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    source_refs: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
