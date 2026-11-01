"""Grant the Worker exact TXT Parser read/update authority."""

from alembic import op

revision: str = "0021_txt_parser_worker_access"
down_revision: str | None = "0020_file_upload_allocations"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "GRANT SELECT, UPDATE ON TABLE public.jobs, public.context_sources, "
        "public.context_source_versions TO aria_worker"
    )
    op.execute("GRANT SELECT ON TABLE public.outbox_events TO aria_worker")

    for table_name in ("jobs", "context_sources", "context_source_versions"):
        op.execute(
            f"""
            CREATE POLICY {table_name}_parser_worker_select
            ON public.{table_name}
            FOR SELECT
            TO aria_worker
            USING (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table_name}_parser_worker_update
            ON public.{table_name}
            FOR UPDATE
            TO aria_worker
            USING (true)
            WITH CHECK (true)
            """
        )

    op.execute(
        """
        CREATE POLICY outbox_events_parser_worker_select
        ON public.outbox_events
        FOR SELECT
        TO aria_worker
        USING (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY outbox_events_parser_worker_select ON public.outbox_events")
    for table_name in ("context_source_versions", "context_sources", "jobs"):
        op.execute(
            f"DROP POLICY {table_name}_parser_worker_update ON public.{table_name}"
        )
        op.execute(
            f"DROP POLICY {table_name}_parser_worker_select ON public.{table_name}"
        )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.outbox_events FROM aria_worker")
    op.execute(
        "REVOKE ALL PRIVILEGES ON TABLE public.jobs, public.context_sources, "
        "public.context_source_versions FROM aria_worker"
    )
