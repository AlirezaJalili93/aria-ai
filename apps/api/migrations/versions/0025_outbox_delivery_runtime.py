"""Add explicit Outbox delivery channels and crash-safe relay leases."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0025_outbox_delivery_runtime"
down_revision: str | None = "0024_ai_failure_accounting"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("delivery_channel", sa.Text(), nullable=True))
    op.add_column(
        "outbox_events",
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.outbox_events
                WHERE event_type NOT IN ('context_added.v1', 'requirement.conflict_detected')
            ) THEN
                RAISE EXCEPTION 'unknown outbox event cannot be classified automatically'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.execute(
        "UPDATE public.outbox_events SET delivery_channel='job_queue' "
        "WHERE event_type='context_added.v1'"
    )
    op.execute(
        "UPDATE public.outbox_events SET delivery_channel='domain_event' "
        "WHERE event_type='requirement.conflict_detected'"
    )
    op.alter_column("outbox_events", "delivery_channel", nullable=False)

    op.drop_constraint("outbox_status", "outbox_events", type_="check")
    op.create_check_constraint(
        "outbox_status",
        "outbox_events",
        "status IN ('pending','published','failed','blocked_unknown_event')",
    )
    op.create_check_constraint(
        "outbox_delivery_channel",
        "outbox_events",
        "delivery_channel IN ('job_queue','domain_event')",
    )
    op.create_check_constraint(
        "outbox_claim_coherence",
        "outbox_events",
        "((claim_id IS NULL AND claimed_at IS NULL AND lease_until IS NULL) OR "
        "(status = 'pending' AND claim_id IS NOT NULL AND claimed_at IS NOT NULL "
        "AND lease_until IS NOT NULL AND lease_until > claimed_at))",
    )
    op.create_check_constraint(
        "outbox_publish_coherence",
        "outbox_events",
        "((status = 'published' AND published_at IS NOT NULL) OR "
        "(status <> 'published' AND published_at IS NULL))",
    )
    op.create_index(
        "ix_outbox_delivery_eligibility",
        "outbox_events",
        ["delivery_channel", "status", "available_at", "lease_until"],
        unique=False,
    )

    op.execute(
        "GRANT UPDATE (status, attempt_count, available_at, published_at, "
        "claim_id, claimed_at, lease_until) ON public.outbox_events TO aria_worker"
    )
    op.execute(
        """
        CREATE POLICY outbox_events_relay_worker_update
        ON public.outbox_events
        FOR UPDATE
        TO aria_worker
        USING (delivery_channel = 'job_queue')
        WITH CHECK (delivery_channel = 'job_queue')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY outbox_events_relay_worker_update ON public.outbox_events")
    op.execute(
        "REVOKE UPDATE (status, attempt_count, available_at, published_at, "
        "claim_id, claimed_at, lease_until) ON public.outbox_events FROM aria_worker"
    )
    op.drop_index("ix_outbox_delivery_eligibility", table_name="outbox_events")
    op.drop_constraint("outbox_publish_coherence", "outbox_events", type_="check")
    op.drop_constraint("outbox_claim_coherence", "outbox_events", type_="check")
    op.drop_constraint("outbox_delivery_channel", "outbox_events", type_="check")
    op.drop_constraint("outbox_status", "outbox_events", type_="check")
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.outbox_events
                WHERE status = 'blocked_unknown_event'
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade while blocked unknown Outbox events exist'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.create_check_constraint(
        "outbox_status",
        "outbox_events",
        "status IN ('pending','published','failed')",
    )
    op.drop_column("outbox_events", "lease_until")
    op.drop_column("outbox_events", "claimed_at")
    op.drop_column("outbox_events", "claim_id")
    op.drop_column("outbox_events", "delivery_channel")
