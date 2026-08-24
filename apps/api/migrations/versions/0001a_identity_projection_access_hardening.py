"""Harden Alembic and Identity tables against implicit Data API grants."""

from alembic import op

revision: str = "0001_identity_access_hardening"
down_revision: str | None = "0001_identity_projection"
branch_labels: str | None = None
depends_on: str | None = None

IDENTITY_TABLES = (
    "public.accounts, public.profiles, public.account_memberships, "
    "public.alembic_version"
)


def upgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        DO $aria$
        DECLARE
            data_api_role text;
        BEGIN
            FOR data_api_role IN
                SELECT rolname
                FROM pg_catalog.pg_roles
                WHERE rolname IN ('anon', 'authenticated')
            LOOP
                EXECUTE format(
                    'REVOKE ALL PRIVILEGES ON TABLE {IDENTITY_TABLES} FROM %I',
                    data_api_role
                );
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                    'REVOKE ALL PRIVILEGES ON TABLES FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $aria$
        DECLARE
            data_api_role text;
        BEGIN
            FOR data_api_role IN
                SELECT rolname
                FROM pg_catalog.pg_roles
                WHERE rolname IN ('anon', 'authenticated')
            LOOP
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                    'GRANT ALL PRIVILEGES ON TABLES TO %I',
                    data_api_role
                );
                EXECUTE format(
                    'GRANT ALL PRIVILEGES ON TABLE {IDENTITY_TABLES} TO %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$;
        """
    )
    op.execute("ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY")
