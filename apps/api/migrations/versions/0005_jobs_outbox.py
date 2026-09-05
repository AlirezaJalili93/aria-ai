"""Create durable Jobs and transactional Outbox persistence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_jobs_outbox"
down_revision: str | None = "0004_context_sources"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("payload_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="job_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="job_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="job_max_attempts"),
        sa.CheckConstraint("attempt_count <= max_attempts", name="job_attempt_limit"),
        sa.CheckConstraint(
            "project_id IS NULL OR account_id IS NOT NULL",
            name="job_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_jobs_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_jobs_project_account_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
    )
    op.create_index(
        "ix_jobs_status_available_at",
        "jobs",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_account_project_created_at",
        "jobs",
        ["account_id", "project_id", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','published','failed')",
            name="outbox_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="outbox_attempt_count"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_outbox_events_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
    )
    op.create_index(
        "ix_outbox_events_status_available_at",
        "outbox_events",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_events_account_created_at",
        "outbox_events",
        ["account_id", sa.text("created_at DESC")],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION public.prevent_outbox_payload_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF OLD.payload IS DISTINCT FROM NEW.payload THEN
                RAISE EXCEPTION 'outbox payload is immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.prevent_outbox_payload_mutation() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_outbox_events_prevent_payload_mutation
        BEFORE UPDATE ON outbox_events
        FOR EACH ROW EXECUTE FUNCTION public.prevent_outbox_payload_mutation()
        """
    )

    for table_name in ("jobs", "outbox_events"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DO $aria$
            DECLARE data_api_role text;
            BEGIN
                FOR data_api_role IN
                    SELECT rolname FROM pg_catalog.pg_roles
                    WHERE rolname IN ('anon', 'authenticated')
                LOOP
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM %I',
                        data_api_role
                    );
                END LOOP;
            END
            $aria$
            """
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_outbox_events_prevent_payload_mutation ON outbox_events")
    op.execute("DROP FUNCTION public.prevent_outbox_payload_mutation()")
    op.drop_index("ix_outbox_events_account_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_available_at", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_jobs_account_project_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status_available_at", table_name="jobs")
    op.drop_table("jobs")
