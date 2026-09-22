"""Distinguish semantic AI Repair executions in the append-only Usage Ledger."""

from alembic import op
import sqlalchemy as sa

revision: str = "0009_usage_repair_number"
down_revision: str | None = "0008_context_items"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "usage_records",
        sa.Column(
            "repair_no",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "usage_repair_no",
        "usage_records",
        "repair_no >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("usage_repair_no", "usage_records", type_="check")
    op.drop_column("usage_records", "repair_no")
