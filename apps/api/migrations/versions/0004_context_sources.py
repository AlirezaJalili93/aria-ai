"""Create tenant-safe Context Sources and immutable Source Versions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_context_sources"
down_revision: str | None = "0003_project_create_idempotency"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_projects_id_account_id",
        "projects",
        ["id", "account_id"],
    )
    op.create_table(
        "context_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("storage_ref", sa.String(length=512), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
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
            "source_type IN ('text','file','message','url_reference')",
            name="context_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('uploaded','parsing','ready','failed','deleted')",
            name="context_source_status",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_context_sources_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_context_sources_project_id_account_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_context_sources_created_by_profiles",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_sources"),
        sa.UniqueConstraint(
            "id",
            "account_id",
            "project_id",
            name="uq_context_sources_id_account_id_project_id",
        ),
    )
    op.create_index(
        "ix_context_sources_account_id_project_id_created_at",
        "context_sources",
        ["account_id", "project_id", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "context_source_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("canonical_text", sa.Text(), nullable=True),
        sa.Column("storage_ref", sa.String(length=512), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("parse_status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version_no >= 1", name="context_source_version_number"),
        sa.CheckConstraint(
            "parse_status IN ('pending','parsing','ready','failed')",
            name="context_source_version_parse_status",
        ),
        sa.CheckConstraint(
            "parse_status <> 'ready' OR (canonical_text IS NOT NULL OR storage_ref IS NOT NULL)",
            name="context_source_version_ready_content",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "account_id", "project_id"],
            ["context_sources.id", "context_sources.account_id", "context_sources.project_id"],
            name="fk_context_source_versions_source_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_source_versions"),
        sa.UniqueConstraint(
            "source_id",
            "version_no",
            name="uq_context_source_versions_source_id_version_no",
        ),
    )
    op.create_index(
        "ix_context_versions_tenant_source_status_no",
        "context_source_versions",
        [
            "account_id",
            "project_id",
            "source_id",
            "parse_status",
            sa.text("version_no DESC"),
        ],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION public.prevent_ready_context_source_version_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF OLD.parse_status = 'ready' THEN
                RAISE EXCEPTION 'ready context source versions are immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.prevent_ready_context_source_version_mutation() FROM PUBLIC"
    )
    op.execute(
        """
        CREATE TRIGGER trg_context_source_versions_prevent_ready_mutation
        BEFORE UPDATE ON context_source_versions
        FOR EACH ROW EXECUTE FUNCTION public.prevent_ready_context_source_version_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_context_sources_set_updated_at
        BEFORE UPDATE ON context_sources
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
        """
    )

    for table_name in ("context_sources", "context_source_versions"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
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
    op.execute("DROP TRIGGER trg_context_sources_set_updated_at ON context_sources")
    op.drop_index(
        "ix_context_versions_tenant_source_status_no",
        table_name="context_source_versions",
    )
    op.drop_table("context_source_versions")
    op.execute("DROP FUNCTION public.prevent_ready_context_source_version_mutation()")
    op.drop_index(
        "ix_context_sources_account_id_project_id_created_at",
        table_name="context_sources",
    )
    op.drop_table("context_sources")
    op.drop_constraint("uq_projects_id_account_id", "projects", type_="unique")
