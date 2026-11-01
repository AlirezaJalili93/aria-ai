"""Extend Gap persistence for the S1-J02-A detection foundation."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_gap_detection"
down_revision: str | None = "0014_gaps"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("gaps", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column(
        "gaps",
        sa.Column("suggested_resolution_type", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "gaps",
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "gap_suggested_resolution_type",
        "gaps",
        "suggested_resolution_type IS NULL OR suggested_resolution_type IN ("
        "'provide_information','clarify_ambiguity','resolve_conflict','make_decision',"
        "'validate_assumption','mitigate_scope_risk')",
    )
    op.create_unique_constraint(
        "uq_jobs_id_account_project",
        "jobs",
        ["id", "account_id", "project_id"],
    )
    op.create_foreign_key(
        "fk_gaps_generation_job_tenant",
        "gaps",
        "jobs",
        ["generation_job_id", "account_id", "project_id"],
        ["id", "account_id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_gaps_account_project_generation_job",
        "gaps",
        ["account_id", "project_id", "generation_job_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_gaps_id_account_project",
        "gaps",
        ["id", "account_id", "project_id"],
    )
    op.create_unique_constraint(
        "uq_requirements_id_account_project",
        "requirements",
        ["id", "account_id", "project_id"],
    )

    op.create_table(
        "gap_requirement_links",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["gap_id", "account_id", "project_id"],
            ["gaps.id", "gaps.account_id", "gaps.project_id"],
            name="fk_gap_requirement_links_gap_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id", "account_id", "project_id"],
            ["requirements.id", "requirements.account_id", "requirements.project_id"],
            name="fk_gap_requirement_links_requirement_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("gap_id", "requirement_id", name="pk_gap_requirement_links"),
    )
    op.create_index(
        "ix_gap_requirement_links_account_project_gap",
        "gap_requirement_links",
        ["account_id", "project_id", "gap_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION public.enforce_gap_requirement_same_snapshot()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM public.gaps AS gap
                JOIN public.requirements AS requirement
                  ON requirement.id = NEW.requirement_id
                 AND requirement.account_id = NEW.account_id
                 AND requirement.project_id = NEW.project_id
                WHERE gap.id = NEW.gap_id
                  AND gap.account_id = NEW.account_id
                  AND gap.project_id = NEW.project_id
                  AND gap.context_version = requirement.context_version
            ) THEN
                RAISE EXCEPTION 'Gap and Requirement must belong to the same Context snapshot'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.enforce_gap_requirement_same_snapshot() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER trg_gap_requirement_links_same_snapshot
        BEFORE INSERT OR UPDATE ON gap_requirement_links
        FOR EACH ROW EXECUTE FUNCTION public.enforce_gap_requirement_same_snapshot()
        """
    )
    op.execute("ALTER TABLE gap_requirement_links ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.gap_requirement_links FROM PUBLIC")
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.gap_requirement_links FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_gap_requirement_links_same_snapshot ON gap_requirement_links")
    op.execute("DROP FUNCTION public.enforce_gap_requirement_same_snapshot()")
    op.drop_index(
        "ix_gap_requirement_links_account_project_gap",
        table_name="gap_requirement_links",
    )
    op.drop_table("gap_requirement_links")
    op.drop_constraint("uq_requirements_id_account_project", "requirements", type_="unique")
    op.drop_constraint("uq_gaps_id_account_project", "gaps", type_="unique")
    op.drop_index("ix_gaps_account_project_generation_job", table_name="gaps")
    op.drop_constraint("fk_gaps_generation_job_tenant", "gaps", type_="foreignkey")
    op.drop_constraint("uq_jobs_id_account_project", "jobs", type_="unique")
    op.drop_constraint("gap_suggested_resolution_type", "gaps", type_="check")
    op.drop_column("gaps", "generation_job_id")
    op.drop_column("gaps", "suggested_resolution_type")
    op.drop_column("gaps", "explanation")
