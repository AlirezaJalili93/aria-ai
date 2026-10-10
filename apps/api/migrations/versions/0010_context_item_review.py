"""Add Context Item review concurrency and filter indexes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_context_item_review"
down_revision: str | None = "0009_usage_repair_number"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "context_items",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.execute(
        """
        CREATE TRIGGER trg_context_items_set_updated_at
        BEFORE UPDATE ON context_items
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
        """
    )
    op.create_index(
        "ix_context_items_current_page",
        "context_items",
        ["account_id", "project_id", "context_version", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_context_items_source_refs_gin",
        "context_items",
        ["source_refs"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"source_refs": "jsonb_path_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_context_items_source_refs_gin", table_name="context_items")
    op.drop_index("ix_context_items_current_page", table_name="context_items")
    op.execute("DROP TRIGGER trg_context_items_set_updated_at ON context_items")
    op.drop_column("context_items", "updated_at")
