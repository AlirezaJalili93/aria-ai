"""Add the synthetic-only Requirement Generation Job runtime boundary."""

from alembic import op

revision: str = "0027_requirement_gen_runtime"
down_revision: str | None = "0026_context_structuring_runtime"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_jobs_active_requirement_generation_revision "
        "ON public.jobs (account_id, project_id, ((payload_ref->>'context_version')::integer)) "
        "WHERE job_type='requirement_generation' AND status IN ('queued','running')"
    )
    op.execute("GRANT SELECT ON TABLE public.context_items TO aria_worker")
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.requirements FROM aria_worker")
    op.execute("REVOKE INSERT ON TABLE public.outbox_events FROM aria_worker")
    op.execute("GRANT SELECT ON TABLE public.requirements TO aria_worker")
    op.execute(
        "GRANT INSERT (id, account_id, project_id, context_version, category, title, "
        "description, priority, status, source_refs, confidence, is_unsupported, "
        "duplicate_group_key, generation_job_id, created_by_type, created_by) "
        "ON public.requirements TO aria_worker"
    )
    op.execute("GRANT UPDATE (source_refs) ON public.requirements TO aria_worker")
    op.execute(
        "GRANT INSERT (id, account_id, aggregate_type, aggregate_id, event_type, "
        "delivery_channel, payload, status, attempt_count, available_at) "
        "ON public.outbox_events TO aria_worker"
    )
    op.execute(
        """
        CREATE POLICY context_items_requirement_generation_worker_select
        ON public.context_items FOR SELECT TO aria_worker USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY requirements_generation_worker_select
        ON public.requirements FOR SELECT TO aria_worker USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY requirements_generation_worker_insert
        ON public.requirements FOR INSERT TO aria_worker
        WITH CHECK (created_by_type='ai' AND created_by IS NULL)
        """
    )
    op.execute(
        """
        CREATE POLICY requirements_generation_worker_update
        ON public.requirements FOR UPDATE TO aria_worker
        USING (true) WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY outbox_events_requirement_generation_worker_insert
        ON public.outbox_events FOR INSERT TO aria_worker
        WITH CHECK (delivery_channel='domain_event')
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY outbox_events_requirement_generation_worker_insert "
        "ON public.outbox_events"
    )
    op.execute("DROP POLICY requirements_generation_worker_update ON public.requirements")
    op.execute("DROP POLICY requirements_generation_worker_insert ON public.requirements")
    op.execute("DROP POLICY requirements_generation_worker_select ON public.requirements")
    op.execute(
        "DROP POLICY context_items_requirement_generation_worker_select "
        "ON public.context_items"
    )
    op.execute("REVOKE INSERT ON TABLE public.outbox_events FROM aria_worker")
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.requirements FROM aria_worker")
    op.execute("REVOKE SELECT ON TABLE public.requirements FROM aria_worker")
    op.execute("REVOKE SELECT ON TABLE public.context_items FROM aria_worker")
    op.execute("DROP INDEX public.uq_jobs_active_requirement_generation_revision")
