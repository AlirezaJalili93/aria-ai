"""Create immutable public Scope Approvals and guest idempotency state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035_scope_approvals"
down_revision: str | None = "0034_scope_share_links"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_scope_versions_id_account_project_version",
        "scope_versions",
        ["id", "account_id", "project_id", "version_no"],
    )
    op.create_unique_constraint(
        "uq_scope_share_links_id_account_project_version",
        "scope_share_links",
        ["id", "account_id", "project_id", "scope_version_id"],
    )
    op.create_table(
        "scope_approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("share_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_hash", sa.String(length=71), nullable=False),
        sa.Column("guest_name", sa.String(length=100), nullable=False),
        sa.Column("explicit_consent", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version_no >= 1", name="scope_approval_version_no"),
        sa.CheckConstraint(
            "version_hash ~ '^sha256:[0-9a-f]{64}$'", name="scope_approval_version_hash"
        ),
        sa.CheckConstraint(
            "char_length(guest_name) BETWEEN 2 AND 100",
            name="scope_approval_guest_name_length",
        ),
        sa.CheckConstraint("guest_name = btrim(guest_name)", name="scope_approval_guest_name_trim"),
        sa.CheckConstraint(
            "guest_name !~ '[[:cntrl:]]'", name="scope_approval_guest_name_controls"
        ),
        sa.CheckConstraint("explicit_consent IS TRUE", name="scope_approval_explicit_consent"),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name="scope_approval_request_hash"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_scope_approvals_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_scope_approvals_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
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
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id", name="pk_scope_approvals"),
        sa.UniqueConstraint("scope_version_id", name="uq_scope_approvals_scope_version"),
        sa.UniqueConstraint(
            "share_link_id",
            "idempotency_key",
            name="uq_scope_approvals_share_link_idempotency",
        ),
    )
    op.create_index(
        "ix_scope_approvals_account_project_version",
        "scope_approvals",
        ["account_id", "project_id", "scope_version_id"],
    )
    op.create_index(
        "ix_scope_approvals_account_approved_at",
        "scope_approvals",
        ["account_id", sa.text("approved_at DESC")],
    )
    op.execute(
        """
        CREATE FUNCTION public.protect_scope_approval()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            RAISE EXCEPTION 'scope approvals are immutable' USING ERRCODE = '55000';
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.protect_scope_approval() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_scope_approvals_protect
        BEFORE UPDATE OR DELETE ON scope_approvals
        FOR EACH ROW EXECUTE FUNCTION public.protect_scope_approval()
        """
    )
    op.execute("ALTER TABLE scope_approvals ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.scope_approvals FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.scope_approvals FROM %I',
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
            IF EXISTS (SELECT 1 FROM public.scope_approvals) THEN
                RAISE EXCEPTION 'cannot downgrade while Scope Approvals exist'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.execute("DROP TRIGGER trg_scope_approvals_protect ON scope_approvals")
    op.execute("DROP FUNCTION public.protect_scope_approval()")
    op.drop_index("ix_scope_approvals_account_approved_at", table_name="scope_approvals")
    op.drop_index("ix_scope_approvals_account_project_version", table_name="scope_approvals")
    op.drop_table("scope_approvals")
    op.drop_constraint(
        "uq_scope_share_links_id_account_project_version",
        "scope_share_links",
        type_="unique",
    )
    op.drop_constraint(
        "uq_scope_versions_id_account_project_version", "scope_versions", type_="unique"
    )
