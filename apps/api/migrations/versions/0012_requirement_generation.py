"""Add the S1-I02 Requirement generation and replay contract."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_requirement_generation"
down_revision: str | None = "0011_requirements"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "requirements",
        sa.Column(
            "is_unsupported", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        "requirements", sa.Column("duplicate_group_key", sa.Text(), nullable=True)
    )
    op.add_column(
        "requirements",
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_requirements_generation_job_id_jobs",
        "requirements",
        "jobs",
        ["generation_job_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_requirements_account_project_generation_job",
        "requirements",
        ["account_id", "project_id", "generation_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_requirements_account_project_generation_job", table_name="requirements"
    )
    op.drop_constraint(
        "fk_requirements_generation_job_id_jobs", "requirements", type_="foreignkey"
    )
    op.drop_column("requirements", "generation_job_id")
    op.drop_column("requirements", "duplicate_group_key")
    op.drop_column("requirements", "is_unsupported")
