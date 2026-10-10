"""Add the synthetic-only Context Structuring Job runtime boundary."""

from alembic import op
import sqlalchemy as sa

revision: str = "0026_context_structuring_runtime"
down_revision: str | None = "0025_outbox_delivery_runtime"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "uq_jobs_active_context_structuring_project",
        "jobs",
        ["account_id", "project_id"],
        unique=True,
        postgresql_where=sa.text(
            "job_type = 'context_structuring' AND status IN ('queued','running')"
        ),
    )

    op.execute("REVOKE UPDATE ON TABLE public.projects FROM aria_worker")
    op.execute("GRANT SELECT ON TABLE public.projects TO aria_worker")
    op.execute(
        "GRANT UPDATE (current_context_version) ON TABLE public.projects TO aria_worker"
    )
    op.execute("GRANT INSERT ON TABLE public.context_items TO aria_worker")
    op.execute(
        """
        CREATE POLICY projects_context_structuring_worker_select
        ON public.projects
        FOR SELECT
        TO aria_worker
        USING (true)
        """
    )
    op.execute(
        """
        CREATE POLICY projects_context_structuring_worker_update
        ON public.projects
        FOR UPDATE
        TO aria_worker
        USING (true)
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY context_items_context_structuring_worker_insert
        ON public.context_items
        FOR INSERT
        TO aria_worker
        WITH CHECK (created_by_type = 'ai' AND created_by IS NULL)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY context_items_context_structuring_worker_insert "
        "ON public.context_items"
    )
    op.execute(
        "DROP POLICY projects_context_structuring_worker_update ON public.projects"
    )
    op.execute(
        "DROP POLICY projects_context_structuring_worker_select ON public.projects"
    )
    op.execute("REVOKE INSERT ON TABLE public.context_items FROM aria_worker")
    op.execute(
        "REVOKE UPDATE (current_context_version) ON TABLE public.projects FROM aria_worker"
    )
    op.execute("REVOKE SELECT ON TABLE public.projects FROM aria_worker")
    op.drop_index(
        "uq_jobs_active_context_structuring_project",
        table_name="jobs",
    )
