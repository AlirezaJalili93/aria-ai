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
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("artifact_type = 'website'", name="artifact_type"),
        CheckConstraint(
            "status IN ('draft','ready','delivered','archived')",
            name="artifact_status",
        ),
        CheckConstraint(
            "(status = 'draft' AND current_version_id IS NULL) OR "
            "(status IN ('ready','delivered','archived') "
            "AND current_version_id IS NOT NULL)",
            name="artifact_current_version_state",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_artifacts_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_version_id", "id", "account_id", "project_id"],
            [
                "artifact_versions.id",
                "artifact_versions.artifact_id",
                "artifact_versions.account_id",
                "artifact_versions.project_id",
            ],
            name="fk_artifacts_current_version_tenant",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        UniqueConstraint("project_id", "artifact_type", name="uq_artifacts_project_type"),
        UniqueConstraint(
            "id", "account_id", "project_id", name="uq_artifacts_id_account_project"
        ),
        Index("ix_artifacts_account_project", "account_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    current_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ArtifactVersionModel(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        CheckConstraint("version_no >= 1", name="artifact_version_number"),
        CheckConstraint(
            "trigger_type IN ('initial','prompt_edit','feedback_revision')",
            name="artifact_version_trigger_type",
        ),
        CheckConstraint(
            "status IN ('queued','generating','validating','ready','failed')",
            name="artifact_version_status",
        ),
        CheckConstraint(
            "schema_name = 'generation_ast_schema' AND schema_version = 'v1'",
            name="artifact_version_schema",
        ),
        CheckConstraint(
            "(version_no = 1 AND parent_version_id IS NULL AND trigger_type = 'initial') OR "
            "(version_no > 1 AND parent_version_id IS NOT NULL "
            "AND trigger_type IN ('prompt_edit','feedback_revision'))",
            name="artifact_version_lineage",
        ),
        CheckConstraint(
            "artifact_hash IS NULL OR artifact_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="artifact_version_hash",
        ),
        CheckConstraint(
            "checkpoint_hash IS NULL OR checkpoint_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="artifact_version_checkpoint_hash",
        ),
        CheckConstraint(
            "(checkpoint_ref IS NULL AND checkpoint_hash IS NULL) OR "
            "(checkpoint_ref IS NOT NULL AND length(btrim(checkpoint_ref)) > 0 "
            "AND checkpoint_hash IS NOT NULL)",
            name="artifact_version_checkpoint_pair",
        ),
        CheckConstraint(
            "(status = 'ready' AND storage_ref IS NOT NULL "
            "AND length(btrim(storage_ref)) > 0 AND artifact_hash IS NOT NULL) OR "
            "(status <> 'ready' AND storage_ref IS NULL AND artifact_hash IS NULL)",
            name="artifact_version_ready_manifest",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_artifact_versions_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["artifact_id", "account_id", "project_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.project_id"],
            name="fk_artifact_versions_artifact_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["scope_version_id", "account_id", "project_id"],
            ["scope_versions.id", "scope_versions.account_id", "scope_versions.project_id"],
            name="fk_artifact_versions_scope_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["parent_version_id", "artifact_id", "account_id", "project_id"],
            [
                "artifact_versions.id",
                "artifact_versions.artifact_id",
                "artifact_versions.account_id",
                "artifact_versions.project_id",
            ],
            name="fk_artifact_versions_parent_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["generation_job_id", "account_id", "project_id"],
            ["jobs.id", "jobs.account_id", "jobs.project_id"],
            name="fk_artifact_versions_generation_job_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "artifact_id", "version_no", name="uq_artifact_versions_artifact_version"
        ),
        UniqueConstraint(
            "generation_job_id", name="uq_artifact_versions_generation_job"
        ),
        UniqueConstraint(
            "id",
            "artifact_id",
            "account_id",
            "project_id",
            name="uq_artifact_versions_identity_tenant",
        ),
        Index(
            "ix_artifact_versions_account_project_created",
            "account_id",
            "project_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_artifact_versions_artifact_version",
            "artifact_id",
            text("version_no DESC"),
        ),
        Index(
            "uq_artifact_versions_one_active_generation",
            "artifact_id",
            unique=True,
            postgresql_where=text("status IN ('queued','generating','validating')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    scope_version_id: Mapped[UUID] = mapped_column(nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    storage_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_name: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_hash: Mapped[str | None] = mapped_column(String(71), nullable=True)
    checkpoint_ref: Mapped[str | None] = mapped_column(Text(), nullable=True)
    checkpoint_hash: Mapped[str | None] = mapped_column(String(71), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    generation_job_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
