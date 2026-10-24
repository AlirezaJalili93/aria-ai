"""Add idempotent Provider attempts and honest unavailable Usage accounting."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0024_ai_failure_accounting"
down_revision: str | None = "0023_provider_price_versions"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "usage_records",
        sa.Column(
            "provider_attempt_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )
    op.alter_column("usage_records", "provider_attempt_id", server_default=None)
    op.create_unique_constraint(
        "uq_usage_records_provider_attempt_id",
        "usage_records",
        ["provider_attempt_id"],
    )

    op.add_column(
        "usage_records",
        sa.Column(
            "accounting_status",
            sa.Text(),
            server_default="complete",
            nullable=False,
        ),
    )
    op.alter_column("usage_records", "accounting_status", server_default=None)
    for column_name, existing_type in (
        ("input_tokens", sa.BigInteger()),
        ("cached_input_tokens", sa.BigInteger()),
        ("output_tokens", sa.BigInteger()),
        ("estimated_cost", sa.NUMERIC(precision=14, scale=8)),
    ):
        op.alter_column(
            "usage_records",
            column_name,
            existing_type=existing_type,
            nullable=True,
        )

    op.create_check_constraint(
        "usage_accounting_status",
        "usage_records",
        "accounting_status IN ('complete','unavailable')",
    )
    op.create_check_constraint(
        "usage_accounting_coherence",
        "usage_records",
        "((accounting_status = 'complete' "
        "AND input_tokens IS NOT NULL "
        "AND cached_input_tokens IS NOT NULL "
        "AND output_tokens IS NOT NULL "
        "AND estimated_cost IS NOT NULL) "
        "OR (accounting_status = 'unavailable' "
        "AND status = 'failed' "
        "AND input_tokens IS NULL "
        "AND cached_input_tokens IS NULL "
        "AND output_tokens IS NULL "
        "AND estimated_cost IS NULL))",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM usage_records
                WHERE accounting_status = 'unavailable'
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade while unavailable Usage accounting exists'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.drop_constraint("usage_accounting_coherence", "usage_records", type_="check")
    op.drop_constraint("usage_accounting_status", "usage_records", type_="check")
    for column_name, existing_type in (
        ("input_tokens", sa.BigInteger()),
        ("cached_input_tokens", sa.BigInteger()),
        ("output_tokens", sa.BigInteger()),
        ("estimated_cost", sa.NUMERIC(precision=14, scale=8)),
    ):
        op.alter_column(
            "usage_records",
            column_name,
            existing_type=existing_type,
            nullable=False,
        )
    op.drop_column("usage_records", "accounting_status")
    op.drop_constraint(
        "uq_usage_records_provider_attempt_id", "usage_records", type_="unique"
    )
    op.drop_column("usage_records", "provider_attempt_id")
