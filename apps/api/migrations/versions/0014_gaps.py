"""Create the canonical tenant-safe Gap domain table."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_gaps"
down_revision: str | None = "0013_requirement_crud"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "gaps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("gap_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column(
            "source_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("context_version >= 1", name="gap_context_version"),
        sa.CheckConstraint(
            "gap_type IN "
            "('missing_information','ambiguity','conflict','decision_required',"
            "'unsupported_assumption','scope_risk')",
            name="gap_type",
        ),
        sa.CheckConstraint(
            "severity IN ('critical','high','medium','low')", name="gap_severity"
        ),
        sa.CheckConstraint(
            "status IN ('open','resolved','dismissed')", name="gap_status"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name="gap_source_refs_array"
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR status = 'resolved'", name="gap_resolved_at_status"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_gaps_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_gaps_project_id_account_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_gaps"),
    )
    op.create_index(
        "ix_gaps_account_project_status_severity",
        "gaps",
        ["account_id", "project_id", "status", "severity"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_gaps_set_updated_at
        BEFORE UPDATE ON gaps
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
        """
    )
    op.execute("ALTER TABLE gaps ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.gaps FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.gaps FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_gaps_set_updated_at ON gaps")
    op.drop_index("ix_gaps_account_project_status_severity", table_name="gaps")
    op.drop_table("gaps")
