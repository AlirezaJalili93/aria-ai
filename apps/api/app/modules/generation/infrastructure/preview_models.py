from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class PreviewRepresentationModel(Base):
    __tablename__ = "preview_representations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_version_id", "artifact_id", "account_id", "project_id"],
            [
                "artifact_versions.id",
                "artifact_versions.artifact_id",
                "artifact_versions.account_id",
                "artifact_versions.project_id",
            ],
            ondelete="RESTRICT",
            name="fk_preview_representation_source",
        ),
        UniqueConstraint(
            "account_id",
            "artifact_version_id",
            "transformer_version",
            "delivery_policy_version",
            name="uq_preview_representation_profile",
        ),
        UniqueConstraint(
            "id",
            "artifact_version_id",
            "account_id",
            "project_id",
            name="uq_preview_representation_tenant_version",
        ),
        CheckConstraint(
            "status IN ('allocated','preparing','ready')", name="preview_representation_status"
        ),
        CheckConstraint(
            "source_hash ~ '^sha256:[0-9a-f]{64}$'", name="preview_representation_source_hash"
        ),
        CheckConstraint(
            "transformer_version='preview_delivery_transformer_v1' AND "
            "delivery_policy_version='preview_delivery_policy_v1'",
            name="preview_profile",
        ),
        CheckConstraint(
            "(status='ready' AND manifest_ref IS NOT NULL AND LENGTH(BTRIM(manifest_ref)) > 0 AND "
            "manifest_hash IS NOT NULL AND manifest_hash ~ '^sha256:[0-9a-f]{64}$') OR "
            "(status<>'ready' AND manifest_ref IS NULL AND manifest_hash IS NULL)",
            name="preview_representation_manifest",
        ),
        Index("ix_preview_representation_tenant", "account_id", "project_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    artifact_version_id: Mapped[UUID] = mapped_column(nullable=False)
    source_hash: Mapped[str] = mapped_column(String(71))
    transformer_version: Mapped[str] = mapped_column(Text)
    delivery_policy_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    manifest_ref: Mapped[str | None] = mapped_column(Text)
    manifest_hash: Mapped[str | None] = mapped_column(String(71))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.user_id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PreviewPublicationModel(Base):
    __tablename__ = "preview_publications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["representation_id", "artifact_version_id", "account_id", "project_id"],
            [
                "preview_representations.id",
                "preview_representations.artifact_version_id",
                "preview_representations.account_id",
                "preview_representations.project_id",
            ],
            ondelete="RESTRICT",
            name="fk_preview_publication_representation",
        ),
        ForeignKeyConstraint(
            ["publish_job_id", "account_id", "project_id"],
            ["jobs.id", "jobs.account_id", "jobs.project_id"],
            ondelete="RESTRICT",
            name="fk_preview_publication_job",
        ),
        UniqueConstraint("publish_job_id", name="uq_preview_publication_job"),
        UniqueConstraint("id", "account_id", "project_id", name="uq_preview_publication_tenant"),
        UniqueConstraint("token_hash", name="uq_preview_publication_capability"),
        CheckConstraint(
            "status IN ('allocated','publishing','ready','revoked')",
            name="preview_publication_status",
        ),
        CheckConstraint("(status='revoked') = (revoked_at IS NOT NULL)", name="preview_revocation"),
        CheckConstraint(
            "(token_hash IS NULL AND expires_at IS NULL AND issued_at IS NULL) OR "
            "(token_hash IS NOT NULL AND token_hash ~ '^[0-9a-f]{64}$' "
            "AND expires_at IS NOT NULL AND "
            "issued_at IS NOT NULL AND expires_at > issued_at AND status IN ('ready','revoked'))",
            name="preview_capability_complete",
        ),
        Index("ix_preview_publication_tenant", "account_id", "project_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    artifact_version_id: Mapped[UUID] = mapped_column(nullable=False)
    representation_id: Mapped[UUID] = mapped_column(nullable=False)
    publish_job_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.user_id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
