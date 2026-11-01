"""Create tenant-scoped immutable Scope Share Links."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_scope_share_links"
down_revision: str | None = "0033_durable_retry_checkpoint"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_scope_versions_id_account_project",
        "scope_versions",
        ["id", "account_id", "project_id"],
    )
    op.create_table(
        "scope_share_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name="scope_share_link_token_hash_size"
        ),
        sa.CheckConstraint("expires_at > created_at", name="scope_share_link_future_expiry"),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="scope_share_link_revocation_chronology",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_scope_share_links_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_share_links_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scope_version_id", "account_id", "project_id"],
            ["scope_versions.id", "scope_versions.account_id", "scope_versions.project_id"],
            name="fk_scope_share_links_scope_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_scope_share_links_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scope_share_links"),
        sa.UniqueConstraint("token_hash", name="uq_scope_share_links_token_hash"),
    )
    op.create_index(
        "ix_scope_share_links_account_project_version",
        "scope_share_links",
        ["account_id", "project_id", "scope_version_id"],
    )
    op.create_index(
        "ix_scope_share_links_account_id",
        "scope_share_links",
        ["account_id", "id"],
    )
    op.create_index(
        "ix_scope_share_links_account_created_at",
        "scope_share_links",
        ["account_id", sa.text("created_at DESC")],
    )
    op.execute(
        """
        CREATE FUNCTION public.protect_scope_share_link()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'scope share links cannot be deleted' USING ERRCODE = '55000';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.account_id IS DISTINCT FROM OLD.account_id
                OR NEW.project_id IS DISTINCT FROM OLD.project_id
                OR NEW.scope_version_id IS DISTINCT FROM OLD.scope_version_id
                OR NEW.token_hash IS DISTINCT FROM OLD.token_hash
                OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
                OR NEW.created_by IS DISTINCT FROM OLD.created_by
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
            THEN
                RAISE EXCEPTION 'scope share link identity is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.revoked_at IS NOT NULL
                AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
            THEN
                RAISE EXCEPTION 'scope share link revocation is terminal'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.protect_scope_share_link() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_scope_share_links_protect
        BEFORE UPDATE OR DELETE ON scope_share_links
        FOR EACH ROW EXECUTE FUNCTION public.protect_scope_share_link()
        """
    )
    op.execute("ALTER TABLE scope_share_links ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.scope_share_links FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.scope_share_links FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.scope_share_links) THEN
                RAISE EXCEPTION 'cannot downgrade while Scope Share Links exist'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.execute("DROP TRIGGER trg_scope_share_links_protect ON scope_share_links")
    op.execute("DROP FUNCTION public.protect_scope_share_link()")
    op.drop_index("ix_scope_share_links_account_created_at", table_name="scope_share_links")
    op.drop_index("ix_scope_share_links_account_id", table_name="scope_share_links")
    op.drop_index("ix_scope_share_links_account_project_version", table_name="scope_share_links")
    op.drop_table("scope_share_links")
    op.drop_constraint("uq_scope_versions_id_account_project", "scope_versions", type_="unique")
