"""Add durable, tenant-scoped AI invocation checkpoints."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0031_ai_invocation_checkpoints"
down_revision: str | None = "0030_generation_input_row_locks"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_invocation_checkpoints",
        sa.Column("provider_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("output_schema_version", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("pricing_version", sa.Text(), nullable=False),
        sa.Column("input_fingerprint", sa.CHAR(length=64), nullable=False),
        sa.Column("retry_no", sa.Integer(), nullable=False),
        sa.Column("repair_no", sa.SmallInteger(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("normalized_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalized_result_hash", sa.CHAR(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("result_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_unknown_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('started','result_ready','finalized','outcome_unknown')",
            name="ai_invocation_checkpoint_status",
        ),
        sa.CheckConstraint(
            "retry_no >= 0 AND repair_no >= 0",
            name="ai_invocation_checkpoint_attempt_numbers",
        ),
        sa.CheckConstraint(
            "input_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ai_invocation_checkpoint_input_fingerprint",
        ),
        sa.CheckConstraint(
            "normalized_result_hash IS NULL OR "
            "normalized_result_hash ~ '^[0-9a-f]{64}$'",
            name="ai_invocation_checkpoint_result_hash",
        ),
        sa.CheckConstraint(
            "((status='started' AND normalized_result IS NULL "
            "AND normalized_result_hash IS NULL AND result_ready_at IS NULL "
            "AND finalized_at IS NULL AND outcome_unknown_at IS NULL) OR "
            "(status='result_ready' AND normalized_result IS NOT NULL "
            "AND normalized_result_hash IS NOT NULL AND result_ready_at IS NOT NULL "
            "AND finalized_at IS NULL AND outcome_unknown_at IS NULL) OR "
            "(status='finalized' AND normalized_result IS NULL "
            "AND normalized_result_hash IS NOT NULL AND result_ready_at IS NOT NULL "
            "AND finalized_at IS NOT NULL AND outcome_unknown_at IS NULL) OR "
            "(status='outcome_unknown' AND normalized_result IS NULL "
            "AND normalized_result_hash IS NULL AND result_ready_at IS NULL "
            "AND finalized_at IS NULL AND outcome_unknown_at IS NOT NULL))",
            name="ai_invocation_checkpoint_state_coherence",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_ai_invocation_checkpoint_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_ai_invocation_checkpoint_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "account_id", "project_id"],
            ["jobs.id", "jobs.account_id", "jobs.project_id"],
            name="fk_ai_invocation_checkpoint_job_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "provider_attempt_id", name="pk_ai_invocation_checkpoints"
        ),
    )
    op.create_index(
        "ix_ai_invocation_checkpoints_job_created",
        "ai_invocation_checkpoints",
        ["account_id", "project_id", "job_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_ai_invocation_checkpoints_recovery",
        "ai_invocation_checkpoints",
        ["status", "created_at"],
    )

    op.execute(
        """
        CREATE FUNCTION aria_internal.enforce_ai_invocation_checkpoint_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF (NEW.provider_attempt_id, NEW.account_id, NEW.project_id, NEW.job_id,
                NEW.task_type, NEW.workflow_version, NEW.prompt_version,
                NEW.output_schema_version, NEW.provider, NEW.model, NEW.pricing_version,
                NEW.input_fingerprint, NEW.retry_no, NEW.repair_no, NEW.correlation_id,
                NEW.created_at)
               IS DISTINCT FROM
               (OLD.provider_attempt_id, OLD.account_id, OLD.project_id, OLD.job_id,
                OLD.task_type, OLD.workflow_version, OLD.prompt_version,
                OLD.output_schema_version, OLD.provider, OLD.model, OLD.pricing_version,
                OLD.input_fingerprint, OLD.retry_no, OLD.repair_no, OLD.correlation_id,
                OLD.created_at) THEN
                RAISE EXCEPTION 'AI invocation checkpoint identity is immutable'
                    USING ERRCODE = '23514';
            END IF;

            IF NOT (
                (OLD.status='started' AND NEW.status IN ('result_ready','outcome_unknown'))
                OR (OLD.status='result_ready' AND NEW.status='finalized')
            ) THEN
                RAISE EXCEPTION 'AI invocation checkpoint transition rejected'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "aria_internal.enforce_ai_invocation_checkpoint_transition() FROM PUBLIC"
    )
    op.execute(
        "CREATE TRIGGER trg_ai_invocation_checkpoint_transition "
        "BEFORE UPDATE ON public.ai_invocation_checkpoints FOR EACH ROW "
        "EXECUTE FUNCTION aria_internal.enforce_ai_invocation_checkpoint_transition()"
    )

    op.execute("ALTER TABLE public.ai_invocation_checkpoints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.ai_invocation_checkpoints FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.ai_invocation_checkpoints FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE '
                    'public.ai_invocation_checkpoints FROM %I',
                    runtime_role
                );
            END LOOP;
        END
        $aria$
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.ai_invocation_checkpoints "
        "TO aria_worker"
    )
    op.execute(
        "CREATE POLICY ai_invocation_checkpoint_worker_select "
        "ON public.ai_invocation_checkpoints FOR SELECT TO aria_worker "
        "USING (account_id::text = "
        "pg_catalog.current_setting('aria.checkpoint_account_id', true))"
    )
    op.execute(
        "CREATE POLICY ai_invocation_checkpoint_worker_insert "
        "ON public.ai_invocation_checkpoints FOR INSERT TO aria_worker "
        "WITH CHECK (account_id::text = "
        "pg_catalog.current_setting('aria.checkpoint_account_id', true))"
    )
    op.execute(
        "CREATE POLICY ai_invocation_checkpoint_worker_update "
        "ON public.ai_invocation_checkpoints FOR UPDATE TO aria_worker "
        "USING (account_id::text = "
        "pg_catalog.current_setting('aria.checkpoint_account_id', true)) "
        "WITH CHECK (account_id::text = "
        "pg_catalog.current_setting('aria.checkpoint_account_id', true))"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.ai_invocation_checkpoints) THEN
                RAISE EXCEPTION
                    'cannot downgrade while AI invocation checkpoints exist'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE ON TABLE public.ai_invocation_checkpoints "
        "FROM aria_worker"
    )
    op.execute(
        "DROP POLICY ai_invocation_checkpoint_worker_update "
        "ON public.ai_invocation_checkpoints"
    )
    op.execute(
        "DROP POLICY ai_invocation_checkpoint_worker_insert "
        "ON public.ai_invocation_checkpoints"
    )
    op.execute(
        "DROP POLICY ai_invocation_checkpoint_worker_select "
        "ON public.ai_invocation_checkpoints"
    )
    op.execute(
        "DROP TRIGGER trg_ai_invocation_checkpoint_transition "
        "ON public.ai_invocation_checkpoints"
    )
    op.execute(
        "DROP FUNCTION aria_internal.enforce_ai_invocation_checkpoint_transition()"
    )
    op.drop_index(
        "ix_ai_invocation_checkpoints_recovery",
        table_name="ai_invocation_checkpoints",
    )
    op.drop_index(
        "ix_ai_invocation_checkpoints_job_created",
        table_name="ai_invocation_checkpoints",
    )
    op.drop_table("ai_invocation_checkpoints")
