"""Add the S1-I03 Requirement CRUD contract."""

import sqlalchemy as sa
from alembic import op

revision: str = "0013_requirement_crud"
down_revision: str | None = "0012_requirement_generation"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "requirements", sa.Column("acceptance_note", sa.Text(), nullable=True)
    )
    op.create_index(
        "ix_requirements_account_project_created",
        "requirements",
        ["account_id", "project_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_requirements_account_project_created", table_name="requirements"
    )
    op.drop_column("requirements", "acceptance_note")
