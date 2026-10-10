"""Create tenant-safe Context Items with validated provenance references."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_context_items"
down_revision: str | None = "0007_usage_records"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "context_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", sa.Text(), server_default="proposed", nullable=False),
        sa.Column("created_by_type", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("context_version >= 1", name="context_item_context_version"),
        sa.CheckConstraint(
            "item_type IN ('fact','assumption','decision','constraint','reference','unknown')",
            name="context_item_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','confirmed','rejected','superseded')",
            name="context_item_status",
        ),
        sa.CheckConstraint(
            "created_by_type IN ('ai','user','system')",
            name="context_item_created_by_type",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="context_item_confidence",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name="context_item_source_refs_array",
        ),
        sa.CheckConstraint(
            "item_type <> 'fact' OR status <> 'confirmed' "
            "OR CASE WHEN jsonb_typeof(source_refs) = 'array' "
            "THEN jsonb_array_length(source_refs) > 0 ELSE false END",
            name="context_item_confirmed_fact_provenance",
        ),
        sa.CheckConstraint(
            "created_by_type <> 'user' OR created_by IS NOT NULL",
            name="context_item_user_creator",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_context_items_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_context_items_project_id_account_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_context_items_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_items"),
    )
    op.create_index(
        "ix_context_items_account_project_version",
        "context_items",
        ["account_id", "project_id", "context_version"],
        unique=False,
    )
    op.create_index(
        "ix_context_items_created_by",
        "context_items",
        ["created_by"],
        unique=False,
    )

    op.execute("ALTER TABLE context_items ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.context_items FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.context_items FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.drop_index("ix_context_items_created_by", table_name="context_items")
    op.drop_index("ix_context_items_account_project_version", table_name="context_items")
    op.drop_table("context_items")
