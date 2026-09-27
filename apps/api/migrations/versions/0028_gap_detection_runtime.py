"""Add the synthetic-only Gap Detection Job runtime boundary."""

from alembic import op

revision: str = "0028_gap_detection_runtime"
down_revision: str | None = "0027_requirement_gen_runtime"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_jobs_active_gap_detection_revision "
        "ON public.jobs (account_id, project_id, ((payload_ref->>'context_version')::integer)) "
        "WHERE job_type='gap_detection' AND status IN ('queued','running')"
    )
    op.execute("REVOKE INSERT ON TABLE public.gaps FROM aria_worker")
    op.execute("REVOKE INSERT ON TABLE public.gap_requirement_links FROM aria_worker")
    op.execute("GRANT SELECT ON TABLE public.gaps TO aria_worker")
    op.execute(
        "GRANT INSERT (id, account_id, project_id, context_version, gap_type, severity, "
        "status, source_refs, explanation, suggested_resolution_type, generation_job_id) "
        "ON public.gaps TO aria_worker"
    )
    op.execute(
        "GRANT INSERT (account_id, project_id, gap_id, requirement_id) "
        "ON public.gap_requirement_links TO aria_worker"
    )
    op.execute(
        """
        CREATE POLICY gaps_detection_worker_select
        ON public.gaps FOR SELECT TO aria_worker USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY gaps_detection_worker_insert
        ON public.gaps FOR INSERT TO aria_worker
        WITH CHECK (status='open' AND resolved_at IS NULL)
        """
    )
    op.execute(
        """
        CREATE POLICY gap_requirement_links_detection_worker_insert
        ON public.gap_requirement_links FOR INSERT TO aria_worker WITH CHECK (true)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY gap_requirement_links_detection_worker_insert "
        "ON public.gap_requirement_links"
    )
    op.execute("DROP POLICY gaps_detection_worker_insert ON public.gaps")
    op.execute("DROP POLICY gaps_detection_worker_select ON public.gaps")
    op.execute("REVOKE INSERT ON TABLE public.gap_requirement_links FROM aria_worker")
    op.execute("REVOKE INSERT, SELECT ON TABLE public.gaps FROM aria_worker")
    op.execute("DROP INDEX public.uq_jobs_active_gap_detection_revision")
