"""Add authenticated Scope Revision lineage and single-use Change Requests."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037_scope_revision_lineage"
down_revision: str | None = "0036_scope_change_requests"
branch_labels: str | None = None
depends_on: str | None = None


def _protect_scope_version_snapshot(*, include_revision_lineage: bool) -> None:
    lineage_checks = """
                OR NEW.revision_of_scope_version_id IS DISTINCT FROM OLD.revision_of_scope_version_id
                OR NEW.change_request_id IS DISTINCT FROM OLD.change_request_id
    """ if include_revision_lineage else ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.protect_scope_version_snapshot()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'scope versions cannot be deleted' USING ERRCODE = '55000';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.account_id IS DISTINCT FROM OLD.account_id
                OR NEW.project_id IS DISTINCT FROM OLD.project_id
                OR NEW.version_no IS DISTINCT FROM OLD.version_no
                OR NEW.context_version IS DISTINCT FROM OLD.context_version
                OR NEW.snapshot_data IS DISTINCT FROM OLD.snapshot_data
                OR NEW.snapshot_hash IS DISTINCT FROM OLD.snapshot_hash
                OR NEW.created_by IS DISTINCT FROM OLD.created_by
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                {lineage_checks}
            THEN
                RAISE EXCEPTION 'scope version snapshot payload is immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.protect_scope_version_snapshot() FROM PUBLIC")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_scope_change_requests_revision_lineage",
        "scope_change_requests",
        ["id", "account_id", "project_id", "scope_version_id"],
    )
    op.add_column(
        "scope_versions",
        sa.Column("revision_of_scope_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "scope_versions",
        sa.Column("change_request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "scope_version_revision_lineage_pair",
        "scope_versions",
        "(revision_of_scope_version_id IS NULL AND change_request_id IS NULL) OR "
        "(revision_of_scope_version_id IS NOT NULL AND change_request_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_scope_versions_revision_parent_tenant",
        "scope_versions",
        "scope_versions",
        ["revision_of_scope_version_id", "account_id", "project_id"],
        ["id", "account_id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_scope_versions_revision_change_request",
        "scope_versions",
        "scope_change_requests",
        ["change_request_id", "account_id", "project_id", "revision_of_scope_version_id"],
        ["id", "account_id", "project_id", "scope_version_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_scope_versions_change_request", "scope_versions", ["change_request_id"]
    )
    op.create_index(
        "ix_scope_versions_revision_parent",
        "scope_versions",
        ["account_id", "project_id", "revision_of_scope_version_id"],
    )
    _protect_scope_version_snapshot(include_revision_lineage=True)


def downgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.scope_versions
                WHERE revision_of_scope_version_id IS NOT NULL OR change_request_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'cannot downgrade while Scope Revision lineage exists'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    _protect_scope_version_snapshot(include_revision_lineage=False)
    op.drop_index("ix_scope_versions_revision_parent", table_name="scope_versions")
    op.drop_constraint("uq_scope_versions_change_request", "scope_versions", type_="unique")
    op.drop_constraint(
        "fk_scope_versions_revision_change_request", "scope_versions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_scope_versions_revision_parent_tenant", "scope_versions", type_="foreignkey"
    )
    op.drop_constraint(
        "scope_version_revision_lineage_pair", "scope_versions", type_="check"
    )
    op.drop_column("scope_versions", "change_request_id")
    op.drop_column("scope_versions", "revision_of_scope_version_id")
    op.drop_constraint(
        "uq_scope_change_requests_revision_lineage",
        "scope_change_requests",
        type_="unique",
    )
