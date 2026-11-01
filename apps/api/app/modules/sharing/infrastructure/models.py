from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models import Base


class ScopeShareLinkModel(Base):
    __tablename__ = "scope_share_links"
    __table_args__ = (
        CheckConstraint("octet_length(token_hash) = 32", name="scope_share_link_token_hash_size"),
        CheckConstraint("expires_at > created_at", name="scope_share_link_future_expiry"),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="scope_share_link_revocation_chronology",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_share_links_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["scope_version_id", "account_id", "project_id"],
            ["scope_versions.id", "scope_versions.account_id", "scope_versions.project_id"],
            name="fk_scope_share_links_scope_version_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("token_hash", name="uq_scope_share_links_token_hash"),
        UniqueConstraint(
            "id",
            "account_id",
            "project_id",
            "scope_version_id",
            name="uq_scope_share_links_id_account_project_version",
        ),
        Index(
            "ix_scope_share_links_account_project_version",
            "account_id",
            "project_id",
            "scope_version_id",
        ),
        Index("ix_scope_share_links_account_id", "account_id", "id"),
        Index("ix_scope_share_links_account_created_at", "account_id", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    scope_version_id: Mapped[UUID] = mapped_column(nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ScopeApprovalModel(Base):
    __tablename__ = "scope_approvals"
    __table_args__ = (
        CheckConstraint("version_no >= 1", name="scope_approval_version_no"),
        CheckConstraint(
            "version_hash ~ '^sha256:[0-9a-f]{64}$'", name="scope_approval_version_hash"
        ),
        CheckConstraint(
            "char_length(guest_name) BETWEEN 2 AND 100",
            name="scope_approval_guest_name_length",
        ),
        CheckConstraint("guest_name = btrim(guest_name)", name="scope_approval_guest_name_trim"),
        CheckConstraint(
            "guest_name !~ '[[:cntrl:]]'", name="scope_approval_guest_name_controls"
        ),
        CheckConstraint("explicit_consent IS TRUE", name="scope_approval_explicit_consent"),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name="scope_approval_request_hash"
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_approvals_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["scope_version_id", "account_id", "project_id", "version_no"],
            [
                "scope_versions.id",
                "scope_versions.account_id",
                "scope_versions.project_id",
                "scope_versions.version_no",
            ],
            name="fk_scope_approvals_scope_version_snapshot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["share_link_id", "account_id", "project_id", "scope_version_id"],
            [
                "scope_share_links.id",
                "scope_share_links.account_id",
                "scope_share_links.project_id",
                "scope_share_links.scope_version_id",
            ],
            name="fk_scope_approvals_share_link_capability",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("scope_version_id", name="uq_scope_approvals_scope_version"),
        UniqueConstraint(
            "share_link_id",
            "idempotency_key",
            name="uq_scope_approvals_share_link_idempotency",
        ),
        Index(
            "ix_scope_approvals_account_project_version",
            "account_id",
            "project_id",
            "scope_version_id",
        ),
        Index("ix_scope_approvals_account_approved_at", "account_id", text("approved_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    scope_version_id: Mapped[UUID] = mapped_column(nullable=False)
    share_link_id: Mapped[UUID] = mapped_column(nullable=False)
    version_no: Mapped[int] = mapped_column(nullable=False)
    version_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(100), nullable=False)
    explicit_consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ScopeChangeRequestModel(Base):
    __tablename__ = "scope_change_requests"
    __table_args__ = (
        CheckConstraint("version_no >= 1", name="scope_change_request_version_no"),
        CheckConstraint(
            "version_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="scope_change_request_version_hash",
        ),
        CheckConstraint(
            "char_length(guest_name) BETWEEN 2 AND 100",
            name="scope_change_request_guest_name_length",
        ),
        CheckConstraint(
            "guest_name = btrim(guest_name)",
            name="scope_change_request_guest_name_trim",
        ),
        CheckConstraint(
            "guest_name !~ '[[:cntrl:]]'",
            name="scope_change_request_guest_name_controls",
        ),
        CheckConstraint(
            "char_length(comment) BETWEEN 1 AND 4000",
            name="scope_change_request_comment_length",
        ),
        CheckConstraint(
            "comment = btrim(comment)",
            name="scope_change_request_comment_trim",
        ),
        CheckConstraint(
            "regexp_replace(comment, E'\\n', '', 'g') !~ '[[:cntrl:]]'",
            name="scope_change_request_comment_controls",
        ),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="scope_change_request_request_hash",
        ),
        ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_change_requests_project_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["scope_version_id", "account_id", "project_id", "version_no"],
            [
                "scope_versions.id",
                "scope_versions.account_id",
                "scope_versions.project_id",
                "scope_versions.version_no",
            ],
            name="fk_scope_change_requests_scope_version_snapshot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["share_link_id", "account_id", "project_id", "scope_version_id"],
            [
                "scope_share_links.id",
                "scope_share_links.account_id",
                "scope_share_links.project_id",
                "scope_share_links.scope_version_id",
            ],
            name="fk_scope_change_requests_share_link_capability",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "scope_version_id",
            name="uq_scope_change_requests_scope_version",
        ),
        UniqueConstraint(
            "id",
            "account_id",
            "project_id",
            "scope_version_id",
            name="uq_scope_change_requests_revision_lineage",
        ),
        UniqueConstraint(
            "share_link_id",
            "idempotency_key",
            name="uq_scope_change_requests_share_link_idempotency",
        ),
        Index(
            "ix_scope_change_requests_account_project_version",
            "account_id",
            "project_id",
            "scope_version_id",
        ),
        Index(
            "ix_scope_change_requests_account_requested_at",
            "account_id",
            text("requested_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    scope_version_id: Mapped[UUID] = mapped_column(nullable=False)
    share_link_id: Mapped[UUID] = mapped_column(nullable=False)
    version_no: Mapped[int] = mapped_column(nullable=False)
    version_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(100), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
