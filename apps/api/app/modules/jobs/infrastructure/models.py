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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="job_status",
        ),
        CheckConstraint("attempt_count >= 0", name="job_attempt_count"),
        CheckConstraint("max_attempts >= 1", name="job_max_attempts"),
        CheckConstraint("attempt_count <= max_attempts", name="job_attempt_limit"),
        CheckConstraint("project_id IS NULL OR account_id IS NOT NULL", name="job_project_tenant"),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_jobs_project_account_projects",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["retry_of_job_id", "account_id", "project_id"],
            ["jobs.id", "jobs.account_id", "jobs.project_id"],
            name="fk_jobs_retry_parent_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "retry_of_job_id IS NULL OR retry_of_job_id <> id", name="job_retry_parent"
        ),
        UniqueConstraint("id", "account_id", "project_id", name="uq_jobs_id_account_project"),
        UniqueConstraint("retry_of_job_id", name="uq_jobs_retry_of_job_id"),
        Index("ix_jobs_status_available_at", "status", "available_at"),
        Index(
            "ix_jobs_account_project_created_at",
            "account_id",
            "project_id",
            text("created_at DESC"),
        ),
        Index(
            "uq_jobs_active_context_source_version",
            "account_id",
            "project_id",
            text("(payload_ref ->> 'source_version_id')"),
            unique=True,
            postgresql_where=text(
                "job_type = 'context_source_parse' AND status IN ('queued','running')"
            ),
        ),
        Index(
            "uq_jobs_active_context_structuring_project",
            "account_id",
            "project_id",
            unique=True,
            postgresql_where=text(
                "job_type = 'context_structuring' AND status IN ('queued','running')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    project_id: Mapped[UUID | None] = mapped_column(nullable=True)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    payload_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_job_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','published','failed','blocked_unknown_event')",
            name="outbox_status",
        ),
        CheckConstraint("attempt_count >= 0", name="outbox_attempt_count"),
        CheckConstraint(
            "delivery_channel IN ('job_queue','domain_event')",
            name="outbox_delivery_channel",
        ),
        CheckConstraint(
            "((claim_id IS NULL AND claimed_at IS NULL AND lease_until IS NULL) OR "
            "(status = 'pending' AND claim_id IS NOT NULL AND claimed_at IS NOT NULL "
            "AND lease_until IS NOT NULL AND lease_until > claimed_at))",
            name="outbox_claim_coherence",
        ),
        CheckConstraint(
            "((status = 'published' AND published_at IS NOT NULL) OR "
            "(status <> 'published' AND published_at IS NULL))",
            name="outbox_publish_coherence",
        ),
        Index("ix_outbox_events_status_available_at", "status", "available_at"),
        Index(
            "ix_outbox_delivery_eligibility",
            "delivery_channel",
            "status",
            "available_at",
            "lease_until",
        ),
        Index(
            "ix_outbox_events_account_created_at",
            "account_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_channel: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_id: Mapped[UUID | None] = mapped_column(nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
