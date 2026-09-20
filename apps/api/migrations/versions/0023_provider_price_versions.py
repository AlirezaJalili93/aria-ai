"""Add immutable Provider price catalog and bind Usage history to it."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_provider_price_versions"
down_revision: str | None = "0022_context_source_management"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "provider_price_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("pricing_version", sa.Text(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("input_rate_per_1m", sa.NUMERIC(precision=20, scale=8), nullable=False),
        sa.Column(
            "cached_input_rate_per_1m", sa.NUMERIC(precision=20, scale=8), nullable=False
        ),
        sa.Column("output_rate_per_1m", sa.NUMERIC(precision=20, scale=8), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("input_rate_per_1m >= 0", name="provider_price_input_rate"),
        sa.CheckConstraint(
            "cached_input_rate_per_1m >= 0", name="provider_price_cached_input_rate"
        ),
        sa.CheckConstraint("output_rate_per_1m >= 0", name="provider_price_output_rate"),
        sa.PrimaryKeyConstraint("id", name="pk_provider_price_versions"),
        sa.UniqueConstraint(
            "provider", "model", "pricing_version", name="uq_provider_prices_identity"
        ),
        sa.UniqueConstraint(
            "provider", "model", "effective_from", name="uq_provider_prices_effective_from"
        ),
    )
    op.execute(
        """
        CREATE FUNCTION public.prevent_provider_price_version_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            RAISE EXCEPTION 'provider price versions are append-only'
                USING ERRCODE = '55000';
        END
        $aria$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.prevent_provider_price_version_mutation() FROM PUBLIC"
    )
    op.execute(
        """
        CREATE TRIGGER trg_provider_price_versions_prevent_mutation
        BEFORE UPDATE OR DELETE ON provider_price_versions
        FOR EACH ROW EXECUTE FUNCTION public.prevent_provider_price_version_mutation()
        """
    )

    op.execute("ALTER TABLE provider_price_versions ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.provider_price_versions FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.provider_price_versions FROM %I',
                    runtime_role
                );
            END LOOP;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.provider_price_versions FROM aria_worker")
    op.execute("GRANT SELECT ON TABLE public.provider_price_versions TO aria_worker")
    op.execute(
        """
        CREATE POLICY provider_price_versions_worker_select
        ON provider_price_versions
        FOR SELECT
        TO aria_worker
        USING (true)
        """
    )

    op.execute(
        "ALTER TABLE usage_records ADD CONSTRAINT usage_cached_input_subset "
        "CHECK (cached_input_tokens <= input_tokens) NOT VALID"
    )
    op.execute(
        "ALTER TABLE usage_records ADD CONSTRAINT fk_usage_records_provider_price "
        "FOREIGN KEY (provider, model, pricing_version) "
        "REFERENCES provider_price_versions (provider, model, pricing_version) "
        "ON DELETE RESTRICT NOT VALID"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE usage_records DROP CONSTRAINT fk_usage_records_provider_price")
    op.execute("ALTER TABLE usage_records DROP CONSTRAINT usage_cached_input_subset")
    op.execute(
        "DROP POLICY provider_price_versions_worker_select ON provider_price_versions"
    )
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.provider_price_versions FROM aria_worker")
    op.execute(
        "DROP TRIGGER trg_provider_price_versions_prevent_mutation ON provider_price_versions"
    )
    op.execute("DROP FUNCTION public.prevent_provider_price_version_mutation()")
    op.drop_table("provider_price_versions")
