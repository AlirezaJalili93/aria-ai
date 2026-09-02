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


class ContextSourceModel(Base):
    __tablename__ = "context_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('text','file','message','url_reference')",
            name="context_source_type",
        ),
        CheckConstraint(
            "status IN ('uploaded','parsing','ready','failed','deleted')",
            name="context_source_status",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_context_sources_project_id_account_id_projects",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id",
            "account_id",
            "project_id",
            name="uq_context_sources_id_account_id_project_id",
        ),
        Index(
            "ix_context_sources_account_id_project_id_created_at",
            "account_id",
            "project_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.user_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContextSourceVersionModel(Base):
    __tablename__ = "context_source_versions"
    __table_args__ = (
        CheckConstraint("version_no >= 1", name="context_source_version_number"),
        CheckConstraint(
            "parse_status IN ('pending','parsing','ready','failed')",
            name="context_source_version_parse_status",
        ),
        CheckConstraint(
            "parse_status <> 'ready' OR (canonical_text IS NOT NULL OR storage_ref IS NOT NULL)",
            name="context_source_version_ready_content",
        ),
        ForeignKeyConstraint(
            ["source_id", "account_id", "project_id"],
            ["context_sources.id", "context_sources.account_id", "context_sources.project_id"],
            name="fk_context_source_versions_source_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "source_id", "version_no", name="uq_context_source_versions_source_id_version_no"
        ),
        Index(
            "ix_context_versions_tenant_source_status_no",
            "account_id",
            "project_id",
            "source_id",
            "parse_status",
            text("version_no DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version_metadata: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
