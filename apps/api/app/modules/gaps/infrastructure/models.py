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
    Text,
    UniqueConstraint,
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
        CheckConstraint("severity IN ('critical','high','medium','low')", name="gap_severity"),
        CheckConstraint("status IN ('open','resolved','dismissed')", name="gap_status"),
        CheckConstraint("jsonb_typeof(source_refs) = 'array'", name="gap_source_refs_array"),
        CheckConstraint(
            "resolved_at IS NULL OR status = 'resolved'", name="gap_resolved_at_status"
        ),
        CheckConstraint(
            "suggested_resolution_type IS NULL OR suggested_resolution_type IN ("
            "'provide_information','clarify_ambiguity','resolve_conflict','make_decision',"
            "'validate_assumption','mitigate_scope_risk')",
            name="gap_suggested_resolution_type",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_gaps_project_id_account_id_projects",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["generation_job_id", "account_id", "project_id"],
            ["jobs.id", "jobs.account_id", "jobs.project_id"],
            name="fk_gaps_generation_job_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "account_id", "project_id", name="uq_gaps_id_account_project"),
        Index(
            "ix_gaps_account_project_status_severity",
            "account_id",
            "project_id",
            "status",
            "severity",
        ),
        Index(
            "ix_gaps_account_project_generation_job",
            "account_id",
            "project_id",
            "generation_job_id",
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
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_resolution_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    generation_job_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GapRequirementLinkModel(Base):
    __tablename__ = "gap_requirement_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["gap_id", "account_id", "project_id"],
            ["gaps.id", "gaps.account_id", "gaps.project_id"],
            name="fk_gap_requirement_links_gap_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_id", "account_id", "project_id"],
            ["requirements.id", "requirements.account_id", "requirements.project_id"],
            name="fk_gap_requirement_links_requirement_tenant",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_gap_requirement_links_account_project_gap",
            "account_id",
            "project_id",
            "gap_id",
        ),
    )

    account_id: Mapped[UUID] = mapped_column(primary_key=False, nullable=False)
    project_id: Mapped[UUID] = mapped_column(primary_key=False, nullable=False)
    gap_id: Mapped[UUID] = mapped_column(primary_key=True, nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(primary_key=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClarificationModel(Base):
    __tablename__ = "clarifications"
    __table_args__ = (
        CheckConstraint("status IN ('open','answered','ignored')", name="clarification_status"),
        CheckConstraint(
            "created_by_type IN ('ai','user','system')", name="clarification_creator_type"
        ),
        CheckConstraint(
            "created_by_type <> 'user' OR created_by IS NOT NULL",
            name="clarification_user_creator",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_clarifications_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["gap_id", "account_id", "project_id"],
            ["gaps.id", "gaps.account_id", "gaps.project_id"],
            name="fk_clarifications_gap_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "account_id", "project_id", "gap_id", name="uq_clarifications_tenant_gap"
        ),
        Index(
            "ix_clarifications_account_project_gap_status",
            "account_id",
            "project_id",
            "gap_id",
            "status",
        ),
        Index(
            "ux_clarifications_open_question",
            "account_id",
            "project_id",
            "gap_id",
            "question_text",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    gap_id: Mapped[UUID] = mapped_column(nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    created_by_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClarificationResolutionModel(Base):
    __tablename__ = "clarification_resolutions"
    __table_args__ = (
        CheckConstraint(
            "resolution_type IN "
            "('provided_information','internal_decision','accepted_assumption','ignored')",
            name="clarification_resolution_type",
        ),
        CheckConstraint("author_type IN ('user','client')", name="clarification_author_type"),
        CheckConstraint(
            "((resolution_type IN ('provided_information','internal_decision')) "
            "AND answer_text IS NOT NULL AND btrim(answer_text) <> '') OR "
            "((resolution_type IN ('accepted_assumption','ignored')) AND answer_text IS NULL)",
            name="clarification_resolution_answer",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_clarification_resolutions_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["gap_id", "account_id", "project_id"],
            ["gaps.id", "gaps.account_id", "gaps.project_id"],
            name="fk_clarification_resolutions_gap_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clarification_id", "account_id", "project_id", "gap_id"],
            [
                "clarifications.id",
                "clarifications.account_id",
                "clarifications.project_id",
                "clarifications.gap_id",
            ],
            name="fk_clarification_resolutions_clarification_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("clarification_id", name="uq_clarification_resolutions_clarification"),
        Index(
            "ix_clarification_resolutions_account_project_gap",
            "account_id",
            "project_id",
            "gap_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    gap_id: Mapped[UUID] = mapped_column(nullable=False)
    clarification_id: Mapped[UUID] = mapped_column(nullable=False)
    resolution_type: Mapped[str] = mapped_column(String(30), nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_type: Mapped[str] = mapped_column(String(20), nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=True
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
