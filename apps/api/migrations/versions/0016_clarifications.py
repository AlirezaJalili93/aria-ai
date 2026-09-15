"""Create the canonical J03-A Clarification and Resolution audit model."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_clarifications"
down_revision: str | None = "0015_gap_detection"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "clarifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("created_by_type", sa.String(length=20), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('open','answered','ignored')", name="clarification_status"
        ),
        sa.CheckConstraint(
            "created_by_type IN ('ai','user','system')", name="clarification_creator_type"
        ),
        sa.CheckConstraint(
            "created_by_type <> 'user' OR created_by IS NOT NULL",
            name="clarification_user_creator",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_clarifications_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_clarifications_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["gap_id", "account_id", "project_id"],
            ["gaps.id", "gaps.account_id", "gaps.project_id"],
            name="fk_clarifications_gap_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_clarifications_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clarifications"),
        sa.UniqueConstraint(
            "id", "account_id", "project_id", "gap_id", name="uq_clarifications_tenant_gap"
        ),
    )
    op.create_index(
        "ix_clarifications_account_project_gap_status",
        "clarifications",
        ["account_id", "project_id", "gap_id", "status"],
        unique=False,
    )
    op.create_index(
        "ux_clarifications_open_question",
        "clarifications",
        ["account_id", "project_id", "gap_id", "question_text"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.execute(
        "CREATE TRIGGER trg_clarifications_set_updated_at "
        "BEFORE UPDATE ON clarifications FOR EACH ROW "
        "EXECUTE FUNCTION public.set_updated_at()"
    )

    op.create_table(
        "clarification_resolutions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clarification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolution_type", sa.String(length=30), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("author_type", sa.String(length=20), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resolution_type IN "
            "('provided_information','internal_decision','accepted_assumption','ignored')",
            name="clarification_resolution_type",
        ),
        sa.CheckConstraint(
            "author_type IN ('user','client')", name="clarification_author_type"
        ),
        sa.CheckConstraint(
            "((resolution_type IN ('provided_information','internal_decision')) "
            "AND answer_text IS NOT NULL AND btrim(answer_text) <> '') OR "
            "((resolution_type IN ('accepted_assumption','ignored')) AND answer_text IS NULL)",
            name="clarification_resolution_answer",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_clarification_resolutions_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_clarification_resolutions_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["gap_id", "account_id", "project_id"],
            ["gaps.id", "gaps.account_id", "gaps.project_id"],
            name="fk_clarification_resolutions_gap_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["clarification_id", "account_id", "project_id", "gap_id"],
            [
                "clarifications.id",
                "clarifications.account_id",
                "clarifications.project_id",
                "clarifications.gap_id",
            ],
            name="fk_clarification_resolutions_clarification_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["profiles.user_id"],
            name="fk_clarification_resolutions_author_profiles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["profiles.user_id"],
            name="fk_clarification_resolutions_actor_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clarification_resolutions"),
        sa.UniqueConstraint(
            "clarification_id", name="uq_clarification_resolutions_clarification"
        ),
    )
    op.create_index(
        "ix_clarification_resolutions_account_project_gap",
        "clarification_resolutions",
        ["account_id", "project_id", "gap_id"],
        unique=False,
    )
    for table_name in ("clarifications", "clarification_resolutions"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM PUBLIC")
        op.execute(
            f"""
            DO $aria$
            DECLARE data_api_role text;
            BEGIN
                FOR data_api_role IN
                    SELECT rolname FROM pg_catalog.pg_roles
                    WHERE rolname IN ('anon', 'authenticated')
                LOOP
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM %I',
                        data_api_role
                    );
                END LOOP;
            END
            $aria$
            """
        )


def downgrade() -> None:
    op.drop_index(
        "ix_clarification_resolutions_account_project_gap",
        table_name="clarification_resolutions",
    )
    op.drop_table("clarification_resolutions")
    op.execute("DROP TRIGGER trg_clarifications_set_updated_at ON clarifications")
    op.drop_index("ux_clarifications_open_question", table_name="clarifications")
    op.drop_index(
        "ix_clarifications_account_project_gap_status", table_name="clarifications"
    )
    op.drop_table("clarifications")
