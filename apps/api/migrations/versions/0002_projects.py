"""Create Projects and establish database-managed mutable timestamps."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_projects"
down_revision: str | None = "0001_identity_access_hardening"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.set_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.set_updated_at() FROM PUBLIC")

    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("project_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column(
            "current_context_version",
            sa.Integer(),
            server_default="0",
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "project_type IN ('landing','corporate','portfolio')",
            name="project_type",
        ),
        sa.CheckConstraint(
            "status IN "
            "('draft','active','awaiting_approval','approved','generating','delivered','archived')",
            name="project_status",
        ),
        sa.CheckConstraint(
            "current_context_version >= 0",
            name="project_current_context_version",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_projects_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["profiles.user_id"],
            name="fk_projects_owner_id_profiles",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index(
        "ix_projects_account_id_created_at",
        "projects",
        ["account_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_projects_account_id_status",
        "projects",
        ["account_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_projects_account_id_project_type",
        "projects",
        ["account_id", "project_type"],
        unique=False,
    )

    for table_name in ("accounts", "profiles", "projects"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_set_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
            """
        )

    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
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
                    'REVOKE ALL PRIVILEGES ON TABLE public.projects FROM %I',
                    data_api_role
                );
            END LOOP;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_accounts_set_updated_at ON accounts")
    op.execute("DROP TRIGGER trg_profiles_set_updated_at ON profiles")
    op.execute("DROP TRIGGER trg_projects_set_updated_at ON projects")
    op.drop_index("ix_projects_account_id_project_type", table_name="projects")
    op.drop_index("ix_projects_account_id_status", table_name="projects")
    op.drop_index("ix_projects_account_id_created_at", table_name="projects")
    op.drop_table("projects")
    op.execute("DROP FUNCTION public.set_updated_at()")
