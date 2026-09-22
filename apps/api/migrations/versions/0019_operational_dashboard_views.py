"""Create least-privilege operational dashboard views for S1-L02."""

from alembic import op

revision: str = "0019_operational_dashboard_views"
down_revision: str | None = "0018_scope_versions"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'aria_observer'
            ) THEN
                CREATE ROLE aria_observer
                    LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
                    NOREPLICATION NOBYPASSRLS;
            END IF;
        END
        $aria$
        """
    )
    op.execute(
        """
        ALTER ROLE aria_observer
            LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS
        """
    )
    op.execute("CREATE SCHEMA observability")
    op.execute("REVOKE ALL ON SCHEMA observability FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM aria_observer")

    op.execute(
        """
        CREATE VIEW observability.job_health
        WITH (security_barrier = true)
        AS
        SELECT
            transaction_timestamp() AS observed_at,
            count(*) FILTER (WHERE status = 'queued')::bigint AS queued_count,
            EXTRACT(
                EPOCH FROM (
                    transaction_timestamp()
                    - min(created_at) FILTER (WHERE status = 'queued')
                )
            )::double precision AS oldest_queued_job_age_seconds
        FROM public.jobs
        """
    )
    op.execute(
        """
        CREATE VIEW observability.job_execution_health
        WITH (security_barrier = true)
        AS
        SELECT
            job_type,
            status,
            created_at,
            EXTRACT(EPOCH FROM (finished_at - started_at))::double precision
                AS execution_duration_seconds
        FROM public.jobs
        WHERE status IN ('succeeded', 'failed')
          AND started_at IS NOT NULL
          AND finished_at IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE VIEW observability.outbox_health
        WITH (security_barrier = true)
        AS
        SELECT
            transaction_timestamp() AS observed_at,
            count(*) FILTER (WHERE published_at IS NULL)::bigint AS pending_count,
            EXTRACT(
                EPOCH FROM (
                    transaction_timestamp()
                    - min(created_at) FILTER (WHERE published_at IS NULL)
                )
            )::double precision AS oldest_pending_age_seconds
        FROM public.outbox_events
        """
    )
    op.execute(
        """
        CREATE VIEW observability.ai_cost_summary
        WITH (security_barrier = true)
        AS
        SELECT
            (created_at AT TIME ZONE 'UTC')::date AS usage_day,
            project_id,
            task_type,
            currency,
            count(*)::bigint AS execution_count,
            sum(estimated_cost) AS estimated_cost
        FROM public.usage_records
        GROUP BY (created_at AT TIME ZONE 'UTC')::date, project_id, task_type, currency
        """
    )

    op.execute(
        """
        CREATE INDEX ix_jobs_queued_created_at
        ON public.jobs (created_at)
        WHERE status = 'queued'
        """
    )
    op.execute(
        """
        CREATE INDEX ix_outbox_events_unpublished_created_at
        ON public.outbox_events (created_at)
        WHERE published_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_usage_records_created_task_project
        ON public.usage_records (created_at, task_type, project_id)
        """
    )

    op.execute("GRANT USAGE ON SCHEMA observability TO aria_observer")
    for view_name in (
        "job_health",
        "job_execution_health",
        "outbox_health",
        "ai_cost_summary",
    ):
        op.execute(f"REVOKE ALL ON observability.{view_name} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON observability.{view_name} TO aria_observer")

    op.execute(
        """
        DO $aria$
        DECLARE data_api_role text;
        BEGIN
            FOR data_api_role IN
                SELECT rolname FROM pg_catalog.pg_roles
                WHERE rolname IN ('anon', 'authenticated')
            LOOP
                EXECUTE format(
                    'REVOKE ALL ON SCHEMA observability FROM %I', data_api_role
                );
                EXECUTE format(
                    'REVOKE ALL ON ALL TABLES IN SCHEMA observability FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA observability FROM aria_observer")
    op.execute("REVOKE ALL ON SCHEMA observability FROM aria_observer")
    op.execute("DROP VIEW observability.ai_cost_summary")
    op.execute("DROP VIEW observability.outbox_health")
    op.execute("DROP VIEW observability.job_execution_health")
    op.execute("DROP VIEW observability.job_health")
    op.execute("DROP SCHEMA observability")
    op.execute("DROP INDEX public.ix_usage_records_created_task_project")
    op.execute("DROP INDEX public.ix_outbox_events_unpublished_created_at")
    op.execute("DROP INDEX public.ix_jobs_queued_created_at")
