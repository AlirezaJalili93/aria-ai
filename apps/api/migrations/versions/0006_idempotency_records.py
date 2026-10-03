"""Create the approved reusable idempotency record store."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_idempotency_records"
down_revision: str | None = "0005_jobs_outbox"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_key", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_idempotency_records_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["profiles.user_id"],
            name="fk_idempotency_records_actor_id_profiles",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint(
            "account_id",
            "actor_id",
            "route_key",
            "idempotency_key",
            name="uq_idempotency_scope_key",
        ),
    )
    op.execute("ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.idempotency_records FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
