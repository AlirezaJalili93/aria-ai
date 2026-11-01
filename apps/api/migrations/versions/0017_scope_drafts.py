"""Create the K01 mutable, version-bound Scope Draft model."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_scope_drafts"
down_revision: str | None = "0016_clarifications"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "scope_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by_type", sa.String(length=10), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("context_version >= 1", name="scope_draft_context_version"),
        sa.CheckConstraint("jsonb_typeof(content) = 'object'", name="scope_draft_content_object"),
        sa.CheckConstraint("updated_by_type IN ('user','ai','system')", name="scope_draft_updated_by_type"),
        sa.CheckConstraint("updated_by_type <> 'user' OR updated_by IS NOT NULL", name="scope_draft_user_updated_by"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_scope_drafts_account_id_accounts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id", "account_id"], ["projects.id", "projects.account_id"], name="fk_scope_drafts_project_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["profiles.user_id"], name="fk_scope_drafts_updated_by_profiles", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_scope_drafts"),
        sa.UniqueConstraint("project_id", "context_version", name="uq_scope_drafts_project_context_version"),
    )
    op.create_index("ix_scope_drafts_account_project_context", "scope_drafts", ["account_id", "project_id", "context_version"])
    op.create_index("ix_scope_drafts_account_updated_at", "scope_drafts", ["account_id", sa.text("updated_at DESC")])
    op.execute("CREATE TRIGGER trg_scope_drafts_set_updated_at BEFORE UPDATE ON scope_drafts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()")
    op.execute("ALTER TABLE scope_drafts ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.scope_drafts FROM PUBLIC")
    op.execute("""
        DO $aria$
        DECLARE data_api_role text;
        BEGIN
            FOR data_api_role IN SELECT rolname FROM pg_catalog.pg_roles WHERE rolname IN ('anon', 'authenticated')
            LOOP
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.scope_drafts FROM %I', data_api_role);
            END LOOP;
        END
        $aria$
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_scope_drafts_set_updated_at ON scope_drafts")
    op.drop_index("ix_scope_drafts_account_updated_at", table_name="scope_drafts")
    op.drop_index("ix_scope_drafts_account_project_context", table_name="scope_drafts")
    op.drop_table("scope_drafts")
