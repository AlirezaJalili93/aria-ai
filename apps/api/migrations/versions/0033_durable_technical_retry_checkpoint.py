"""Add known-failure state and durable retry schedule to AI checkpoints."""

from alembic import op
import sqlalchemy as sa

revision: str = "0033_durable_retry_checkpoint"
down_revision: str | None = "0032_ai01_checkpoint_integration"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "ai_invocation_checkpoints",
        sa.Column("failure_class", sa.Text(), nullable=True),
    )
    op.add_column(
        "ai_invocation_checkpoints",
        sa.Column("retryable", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "ai_invocation_checkpoints",
        sa.Column("retry_not_before", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_invocation_checkpoints",
        sa.Column("failed_known_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.drop_constraint(
        "ai_invocation_checkpoint_status",
        "ai_invocation_checkpoints",
        type_="check",
    )
    op.drop_constraint(
        "ai_invocation_checkpoint_state_coherence",
        "ai_invocation_checkpoints",
        type_="check",
    )
    op.create_check_constraint(
        "ai_invocation_checkpoint_status",
        "ai_invocation_checkpoints",
        "status IN ('started','failed_known','result_ready','finalized','outcome_unknown')",
    )
    op.create_check_constraint(
        "ai_invocation_checkpoint_state_coherence",
        "ai_invocation_checkpoints",
        "((status='started' AND normalized_result IS NULL "
        "AND normalized_result_hash IS NULL AND result_ready_at IS NULL "
        "AND finalized_at IS NULL AND outcome_unknown_at IS NULL "
        "AND failure_class IS NULL AND retryable IS NULL "
        "AND retry_not_before IS NULL AND failed_known_at IS NULL) OR "
        "(status='failed_known' AND normalized_result IS NULL "
        "AND normalized_result_hash IS NULL AND result_ready_at IS NULL "
        "AND finalized_at IS NULL AND outcome_unknown_at IS NULL "
        "AND failure_class='timeout' AND retryable IS TRUE "
        "AND failed_known_at IS NOT NULL "
        "AND ((retry_no=0 AND retry_not_before IS NOT NULL) "
        "OR (retry_no=1 AND retry_not_before IS NULL))) OR "
        "(status='result_ready' AND normalized_result IS NOT NULL "
        "AND normalized_result_hash IS NOT NULL AND result_ready_at IS NOT NULL "
        "AND finalized_at IS NULL AND outcome_unknown_at IS NULL "
        "AND failure_class IS NULL AND retryable IS NULL "
        "AND retry_not_before IS NULL AND failed_known_at IS NULL) OR "
        "(status='finalized' AND normalized_result IS NULL "
        "AND normalized_result_hash IS NOT NULL AND result_ready_at IS NOT NULL "
        "AND finalized_at IS NOT NULL AND outcome_unknown_at IS NULL "
        "AND failure_class IS NULL AND retryable IS NULL "
        "AND retry_not_before IS NULL AND failed_known_at IS NULL) OR "
        "(status='outcome_unknown' AND normalized_result IS NULL "
        "AND normalized_result_hash IS NULL AND result_ready_at IS NULL "
        "AND finalized_at IS NULL AND outcome_unknown_at IS NOT NULL "
        "AND failure_class IS NULL AND retryable IS NULL "
        "AND retry_not_before IS NULL AND failed_known_at IS NULL))",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION aria_internal.enforce_ai_invocation_checkpoint_transition()
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
                (OLD.status='started' AND NEW.status IN
                    ('failed_known','result_ready','outcome_unknown'))
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
    op.create_index(
        "ix_ai_invocation_checkpoints_retry_due",
        "ai_invocation_checkpoints",
        ["retry_not_before"],
        postgresql_where=sa.text("status='failed_known' AND retry_not_before IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.ai_invocation_checkpoints
                WHERE status='failed_known'
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade while known-failure AI checkpoints exist'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.drop_index(
        "ix_ai_invocation_checkpoints_retry_due",
        table_name="ai_invocation_checkpoints",
    )
    op.drop_constraint(
        "ai_invocation_checkpoint_state_coherence",
        "ai_invocation_checkpoints",
        type_="check",
    )
    op.drop_constraint(
        "ai_invocation_checkpoint_status",
        "ai_invocation_checkpoints",
        type_="check",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aria_internal.enforce_ai_invocation_checkpoint_transition()
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
    op.create_check_constraint(
        "ai_invocation_checkpoint_status",
        "ai_invocation_checkpoints",
        "status IN ('started','result_ready','finalized','outcome_unknown')",
    )
    op.create_check_constraint(
        "ai_invocation_checkpoint_state_coherence",
        "ai_invocation_checkpoints",
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
    )
    op.drop_column("ai_invocation_checkpoints", "failed_known_at")
    op.drop_column("ai_invocation_checkpoints", "retry_not_before")
    op.drop_column("ai_invocation_checkpoints", "retryable")
    op.drop_column("ai_invocation_checkpoints", "failure_class")
