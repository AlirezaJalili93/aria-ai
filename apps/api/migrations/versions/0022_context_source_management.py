"""Add Context Source management and explicit parser retry lineage."""

from alembic import op
import sqlalchemy as sa


revision: str = "0022_context_source_management"
down_revision: str | None = "0021_txt_parser_worker_access"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("retry_of_job_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        "job_retry_parent", "jobs", "retry_of_job_id IS NULL OR retry_of_job_id <> id"
    )
    op.create_foreign_key(
        "fk_jobs_retry_parent_tenant",
        "jobs",
        "jobs",
        ["retry_of_job_id", "account_id", "project_id"],
        ["id", "account_id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_jobs_retry_of_job_id", "jobs", ["retry_of_job_id"])
    op.create_index(
        "uq_jobs_active_context_source_version",
        "jobs",
        ["account_id", "project_id", sa.text("(payload_ref ->> 'source_version_id')")],
        unique=True,
        postgresql_where=sa.text(
            "job_type = 'context_source_parse' AND status IN ('queued','running')"
        ),
    )
    op.drop_index(
        "ix_context_sources_account_id_project_id_created_at", table_name="context_sources"
    )
    op.create_index(
        "ix_context_sources_account_id_project_id_created_at",
        "context_sources",
        ["account_id", "project_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_context_sources_account_id_project_id_created_at", table_name="context_sources"
    )
    op.create_index(
        "ix_context_sources_account_id_project_id_created_at",
        "context_sources",
        ["account_id", "project_id", sa.text("created_at DESC")],
    )
    op.drop_index("uq_jobs_active_context_source_version", table_name="jobs")
    op.drop_constraint("uq_jobs_retry_of_job_id", "jobs", type_="unique")
    op.drop_constraint("fk_jobs_retry_parent_tenant", "jobs", type_="foreignkey")
    op.drop_constraint("job_retry_parent", "jobs", type_="check")
    op.drop_column("jobs", "retry_of_job_id")
