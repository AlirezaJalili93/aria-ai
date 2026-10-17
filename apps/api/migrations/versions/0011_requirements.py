"""Create the tenant-safe Requirement domain data contract."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_requirements"
down_revision: str | None = "0010_context_item_review"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column(
            "source_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("created_by_type", sa.String(length=10), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("context_version >= 1", name="requirement_context_version"),
        sa.CheckConstraint(
            "category IN ('functional','content','visual','technical','constraint','business')",
            name="requirement_category",
        ),
        sa.CheckConstraint(
            "priority IN ('must','should','could')", name="requirement_priority"
        ),
        sa.CheckConstraint(
            "status IN ('draft','confirmed','superseded','removed')",
            name="requirement_status",
        ),
        sa.CheckConstraint(
            "created_by_type IN ('ai','user')", name="requirement_created_by_type"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="requirement_confidence",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name="requirement_source_refs_array"
        ),
        sa.CheckConstraint(
            "created_by_type <> 'user' OR created_by IS NOT NULL",
            name="requirement_user_creator",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_requirements_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_requirements_project_id_account_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_requirements_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirements"),
    )
    op.create_index(
        "ix_requirements_account_project_status_category",
        "requirements",
        ["account_id", "project_id", "status", "category"],
        unique=False,
    )
    op.create_index(
        "ix_requirements_created_by", "requirements", ["created_by"], unique=False
    )
    op.execute(
        """
        CREATE TRIGGER trg_requirements_set_updated_at
        BEFORE UPDATE ON requirements
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
        """
    )
    op.execute("ALTER TABLE requirements ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.requirements FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.requirements FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_requirements_set_updated_at ON requirements")
    op.drop_index("ix_requirements_created_by", table_name="requirements")
    op.drop_index(
        "ix_requirements_account_project_status_category", table_name="requirements"
    )
    op.drop_table("requirements")
