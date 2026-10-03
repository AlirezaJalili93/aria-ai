"""Add the controlled synthetic-only Scope Generation Job runtime boundary."""

from alembic import op

revision: str = "0029_scope_generation_runtime"
down_revision: str | None = "0028_gap_detection_runtime"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION public.lock_scope_generation_inputs() RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $aria$
        BEGIN
            LOCK TABLE public.context_items IN SHARE MODE;
            LOCK TABLE public.requirements IN SHARE MODE;
            LOCK TABLE public.gaps IN SHARE MODE;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.lock_scope_generation_inputs() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.lock_scope_generation_inputs() TO aria_worker")
    op.execute(
        "CREATE UNIQUE INDEX uq_jobs_active_scope_generation_revision "
        "ON public.jobs (account_id, project_id, ((payload_ref->>'context_version')::integer)) "
        "WHERE job_type='scope_generation' AND status IN ('queued','running')"
    )
    op.execute("REVOKE INSERT ON TABLE public.scope_drafts FROM aria_worker")
    op.execute("GRANT SELECT ON TABLE public.scope_drafts TO aria_worker")
    op.execute(
        "GRANT INSERT (id, account_id, project_id, context_version, content, "
        "updated_by_type, updated_by) ON public.scope_drafts TO aria_worker"
    )
    op.execute(
        "CREATE POLICY scope_drafts_generation_worker_select "
        "ON public.scope_drafts FOR SELECT TO aria_worker USING (true)"
    )
    op.execute(
        "CREATE POLICY scope_drafts_generation_worker_insert "
        "ON public.scope_drafts FOR INSERT TO aria_worker "
        "WITH CHECK (updated_by_type='ai' AND updated_by IS NULL)"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.lock_scope_generation_inputs()")
    op.execute(
        "DROP POLICY scope_drafts_generation_worker_insert ON public.scope_drafts"
    )
    op.execute(
        "DROP POLICY scope_drafts_generation_worker_select ON public.scope_drafts"
    )
    op.execute("REVOKE INSERT, SELECT ON TABLE public.scope_drafts FROM aria_worker")
    op.execute("DROP INDEX public.uq_jobs_active_scope_generation_revision")
