"""Add durable TXT upload allocations for timeout-safe idempotency."""

import sqlalchemy as sa
from alembic import op

revision: str = "0020_file_upload_allocations"
down_revision: str | None = "0019_operational_dashboard_views"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "file_upload_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("source_version_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('allocated','uploading','committed','recovery_required')",
            name="file_upload_allocation_status",
        ),
        sa.CheckConstraint(
            "(status = 'committed' AND response_status = 202) "
            "OR (status <> 'committed' AND response_status IS NULL)",
            name="file_upload_allocation_response",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_file_upload_allocation_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["profiles.user_id"],
            name="fk_file_upload_allocation_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_file_upload_allocation_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_upload_allocations"),
        sa.UniqueConstraint(
            "account_id",
            "actor_id",
            "project_id",
            "idempotency_key",
            name="uq_file_upload_allocation_scope_key",
        ),
        sa.UniqueConstraint("source_id", name="uq_file_upload_allocation_source"),
        sa.UniqueConstraint(
            "source_version_id", name="uq_file_upload_allocation_source_version"
        ),
        sa.UniqueConstraint("job_id", name="uq_file_upload_allocation_job"),
        sa.UniqueConstraint("object_key", name="uq_file_upload_allocation_object_key"),
    )
    op.create_index(
        "ix_file_upload_allocation_scope_status",
        "file_upload_allocations",
        ["account_id", "project_id", "status"],
    )
    op.execute("ALTER TABLE file_upload_allocations ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE file_upload_allocations FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.file_upload_allocations FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON TABLE file_upload_allocations FROM PUBLIC")
    op.drop_index(
        "ix_file_upload_allocation_scope_status",
        table_name="file_upload_allocations",
    )
    op.drop_table("file_upload_allocations")
