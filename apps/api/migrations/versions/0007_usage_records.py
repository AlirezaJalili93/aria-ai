"""Create the append-only Usage Ledger and its least-privilege writer role."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_usage_records"
down_revision: str | None = "0006_idempotency_records"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'aria_worker'
            ) THEN
                CREATE ROLE aria_worker
                    LOGIN
                    NOINHERIT
                    NOSUPERUSER
                    NOCREATEDB
                    NOCREATEROLE
                    NOREPLICATION
                    NOBYPASSRLS;
            END IF;
        END
        $aria$
        """
    )
    op.execute(
        """
        ALTER ROLE aria_worker
            LOGIN
            NOINHERIT
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS
        """
    )

    op.create_table(
        "usage_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("provider_request_id", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cached_input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("latency_ms", sa.NUMERIC(precision=14, scale=3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("retry_no", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.NUMERIC(precision=14, scale=8), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="USD", nullable=False),
        sa.Column("pricing_version", sa.Text(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("input_tokens >= 0", name="usage_input_tokens"),
        sa.CheckConstraint("cached_input_tokens >= 0", name="usage_cached_input_tokens"),
        sa.CheckConstraint("output_tokens >= 0", name="usage_output_tokens"),
        sa.CheckConstraint("latency_ms >= 0", name="usage_latency_ms"),
        sa.CheckConstraint(
            "status IN ('success','failed','partial')",
            name="usage_status",
        ),
        sa.CheckConstraint("retry_no >= 0", name="usage_retry_no"),
        sa.CheckConstraint("estimated_cost >= 0", name="usage_estimated_cost"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_usage_records_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_usage_records_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_usage_records_job_id_jobs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_records"),
    )
    op.create_index(
        "ix_usage_records_account_created_at",
        "usage_records",
        ["account_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_usage_records_project_id",
        "usage_records",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_usage_records_job_id",
        "usage_records",
        ["job_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION public.prevent_usage_record_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            RAISE EXCEPTION 'usage records are append-only'
                USING ERRCODE = '55000';
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.prevent_usage_record_mutation() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_usage_records_prevent_mutation
        BEFORE UPDATE OR DELETE ON usage_records
        FOR EACH ROW EXECUTE FUNCTION public.prevent_usage_record_mutation()
        """
    )

    op.execute("ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.usage_records FROM PUBLIC")
    op.execute(
        """
        DO $aria$
        DECLARE runtime_role text;
        BEGIN
            FOR runtime_role IN
                SELECT rolname FROM pg_catalog.pg_roles
                WHERE rolname IN ('anon', 'authenticated', 'aria_api')
            LOOP
                EXECUTE format(
                    'REVOKE ALL PRIVILEGES ON TABLE public.usage_records FROM %I',
                    runtime_role
                );
            END LOOP;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.usage_records FROM aria_worker")
    op.execute("GRANT USAGE ON SCHEMA public TO aria_worker")
    op.execute("GRANT INSERT ON TABLE public.usage_records TO aria_worker")
    op.execute(
        """
        CREATE POLICY usage_records_worker_insert
        ON usage_records
        FOR INSERT
        TO aria_worker
        WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY usage_records_worker_insert ON usage_records")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.usage_records FROM aria_worker")
    op.execute("DROP TRIGGER trg_usage_records_prevent_mutation ON usage_records")
    op.execute("DROP FUNCTION public.prevent_usage_record_mutation()")
    op.drop_index("ix_usage_records_job_id", table_name="usage_records")
    op.drop_index("ix_usage_records_project_id", table_name="usage_records")
    op.drop_index("ix_usage_records_account_created_at", table_name="usage_records")
    op.drop_table("usage_records")

