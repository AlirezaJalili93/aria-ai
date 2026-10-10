"""Enforce one durable checkpoint identity per logical AI attempt."""

from alembic import op

revision: str = "0032_ai01_checkpoint_integration"
down_revision: str | None = "0031_ai_invocation_checkpoints"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "uq_ai_invocation_checkpoint_job_attempt",
        "ai_invocation_checkpoints",
        [
            "account_id",
            "project_id",
            "job_id",
            "task_type",
            "retry_no",
            "repair_no",
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ai_invocation_checkpoint_job_attempt",
        table_name="ai_invocation_checkpoints",
    )
