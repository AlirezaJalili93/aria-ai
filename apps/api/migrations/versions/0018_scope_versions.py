"""Create immutable K05 Scope Version snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_scope_versions"
down_revision: str | None = "0017_scope_drafts"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "scope_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=30), server_default="awaiting_approval", nullable=False
        ),
        sa.Column("snapshot_data", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=71), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version_no >= 1", name="scope_version_version_no"),
        sa.CheckConstraint("context_version >= 1", name="scope_version_context_version"),
        sa.CheckConstraint(
            "status IN ('awaiting_approval','approved','changes_requested','superseded')",
            name="scope_version_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(snapshot_data) = 'object'",
            name="scope_version_snapshot_object",
        ),
        sa.CheckConstraint(
            "snapshot_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="scope_version_snapshot_hash",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_scope_versions_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_versions_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_scope_versions_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scope_versions"),
        sa.UniqueConstraint(
            "project_id", "version_no", name="uq_scope_versions_project_version"
        ),
    )
    op.create_index(
        "ix_scope_versions_account_project_version",
        "scope_versions",
        ["account_id", "project_id", sa.text("version_no DESC")],
    )
    op.create_index(
        "ix_scope_versions_account_created_at",
        "scope_versions",
        ["account_id", sa.text("created_at DESC")],
    )
    op.execute(
        """
        CREATE FUNCTION public.protect_scope_version_snapshot()
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
    op.execute(
        """
        CREATE TRIGGER trg_scope_versions_protect_snapshot
        BEFORE UPDATE OR DELETE ON scope_versions
        FOR EACH ROW EXECUTE FUNCTION public.protect_scope_version_snapshot()
        """
    )
    op.execute("ALTER TABLE scope_versions ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.scope_versions FROM PUBLIC")
    op.execute(
        """
        DO $aria$
        DECLARE data_api_role text;
        BEGIN
            FOR data_api_role IN
                SELECT rolname FROM pg_catalog.pg_roles
                WHERE rolname IN ('anon', 'authenticated')
            LOOP
                EXECUTE format(
                    'REVOKE ALL PRIVILEGES ON TABLE public.scope_versions FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_scope_versions_protect_snapshot ON scope_versions")
    op.execute("DROP FUNCTION public.protect_scope_version_snapshot()")
    op.drop_index("ix_scope_versions_account_created_at", table_name="scope_versions")
    op.drop_index("ix_scope_versions_account_project_version", table_name="scope_versions")
    op.drop_table("scope_versions")
