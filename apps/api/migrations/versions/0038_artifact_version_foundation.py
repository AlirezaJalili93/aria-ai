"""Create tenant-scoped Artifact and immutable ArtifactVersion persistence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038_artifact_version_foundation"
down_revision: str | None = "0037_scope_revision_lineage"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_type", sa.String(length=30), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("artifact_type = 'website'", name="artifact_type"),
        sa.CheckConstraint(
            "status IN ('draft','ready','delivered','archived')",
            name="artifact_status",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND current_version_id IS NULL) OR "
            "(status IN ('ready','delivered','archived') "
            "AND current_version_id IS NOT NULL)",
            name="artifact_current_version_state",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_artifacts_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_artifacts_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
        sa.UniqueConstraint(
            "project_id", "artifact_type", name="uq_artifacts_project_type"
        ),
        sa.UniqueConstraint(
            "id", "account_id", "project_id", name="uq_artifacts_id_account_project"
        ),
    )
    op.create_table(
        "artifact_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_ref", sa.Text(), nullable=True),
        sa.Column("schema_name", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("artifact_hash", sa.String(length=71), nullable=True),
        sa.Column("trigger_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("version_no >= 1", name="artifact_version_number"),
        sa.CheckConstraint(
            "trigger_type IN ('initial','prompt_edit','feedback_revision')",
            name="artifact_version_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued','generating','validating','ready','failed')",
            name="artifact_version_status",
        ),
        sa.CheckConstraint(
            "schema_name = 'generation_ast_schema' AND schema_version = 'v1'",
            name="artifact_version_schema",
        ),
        sa.CheckConstraint(
            "(version_no = 1 AND parent_version_id IS NULL AND trigger_type = 'initial') OR "
            "(version_no > 1 AND parent_version_id IS NOT NULL "
            "AND trigger_type IN ('prompt_edit','feedback_revision'))",
            name="artifact_version_lineage",
        ),
        sa.CheckConstraint(
            "artifact_hash IS NULL OR artifact_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="artifact_version_hash",
        ),
        sa.CheckConstraint(
            "(status = 'ready' AND storage_ref IS NOT NULL "
            "AND length(btrim(storage_ref)) > 0 AND artifact_hash IS NOT NULL) OR "
            "(status <> 'ready' AND storage_ref IS NULL AND artifact_hash IS NULL)",
            name="artifact_version_ready_manifest",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_artifact_versions_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "account_id"],
            ["projects.id", "projects.account_id"],
            name="fk_artifact_versions_project_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id", "account_id", "project_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.project_id"],
            name="fk_artifact_versions_artifact_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scope_version_id", "account_id", "project_id"],
            ["scope_versions.id", "scope_versions.account_id", "scope_versions.project_id"],
            name="fk_artifact_versions_scope_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id", "artifact_id", "account_id", "project_id"],
            [
                "artifact_versions.id",
                "artifact_versions.artifact_id",
                "artifact_versions.account_id",
                "artifact_versions.project_id",
            ],
            name="fk_artifact_versions_parent_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id", "account_id", "project_id"],
            ["jobs.id", "jobs.account_id", "jobs.project_id"],
            name="fk_artifact_versions_generation_job_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.user_id"],
            name="fk_artifact_versions_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_versions"),
        sa.UniqueConstraint(
            "artifact_id", "version_no", name="uq_artifact_versions_artifact_version"
        ),
        sa.UniqueConstraint(
            "generation_job_id", name="uq_artifact_versions_generation_job"
        ),
        sa.UniqueConstraint(
            "id",
            "artifact_id",
            "account_id",
            "project_id",
            name="uq_artifact_versions_identity_tenant",
        ),
    )
    op.create_foreign_key(
        "fk_artifacts_current_version_tenant",
        "artifacts",
        "artifact_versions",
        ["current_version_id", "id", "account_id", "project_id"],
        ["id", "artifact_id", "account_id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_artifacts_account_project",
        "artifacts",
        ["account_id", "project_id"],
    )
    op.create_index(
        "ix_artifact_versions_account_project_created",
        "artifact_versions",
        ["account_id", "project_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_artifact_versions_artifact_version",
        "artifact_versions",
        ["artifact_id", sa.text("version_no DESC")],
    )

    op.execute(
        """
        CREATE FUNCTION public.protect_artifact_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        DECLARE target_status text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'artifacts cannot be deleted' USING ERRCODE = '55000';
            END IF;
            IF (NEW.id, NEW.account_id, NEW.project_id, NEW.artifact_type, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.account_id, OLD.project_id, OLD.artifact_type, OLD.created_at)
            THEN
                RAISE EXCEPTION 'artifact identity is immutable' USING ERRCODE = '55000';
            END IF;
            IF NEW.current_version_id IS DISTINCT FROM OLD.current_version_id
                AND NEW.current_version_id IS NOT NULL
            THEN
                SELECT av.status INTO target_status
                FROM public.artifact_versions AS av
                WHERE av.id = NEW.current_version_id
                  AND av.artifact_id = NEW.id
                  AND av.account_id = NEW.account_id
                  AND av.project_id = NEW.project_id;
                IF target_status IS DISTINCT FROM 'ready' THEN
                    RAISE EXCEPTION 'artifact current version must be ready and owned'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            IF OLD.current_version_id IS NOT NULL AND NEW.current_version_id IS NULL THEN
                RAISE EXCEPTION 'artifact current version cannot be cleared'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.protect_artifact_lifecycle() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_artifacts_protect_lifecycle "
        "BEFORE UPDATE OR DELETE ON public.artifacts FOR EACH ROW "
        "EXECUTE FUNCTION public.protect_artifact_lifecycle()"
    )
    op.execute(
        "CREATE TRIGGER trg_artifacts_set_updated_at BEFORE UPDATE ON public.artifacts "
        "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
    )
    op.execute(
        """
        CREATE FUNCTION public.protect_artifact_version()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $aria$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'artifact versions cannot be deleted' USING ERRCODE = '55000';
            END IF;
            IF (NEW.id, NEW.account_id, NEW.project_id, NEW.artifact_id,
                NEW.scope_version_id, NEW.version_no, NEW.parent_version_id,
                NEW.schema_name, NEW.schema_version, NEW.trigger_type,
                NEW.created_by, NEW.generation_job_id, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.account_id, OLD.project_id, OLD.artifact_id,
                OLD.scope_version_id, OLD.version_no, OLD.parent_version_id,
                OLD.schema_name, OLD.schema_version, OLD.trigger_type,
                OLD.created_by, OLD.generation_job_id, OLD.created_at)
            THEN
                RAISE EXCEPTION 'artifact version identity is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.status = 'ready' AND NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'ready artifact versions are immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.protect_artifact_version() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_artifact_versions_protect "
        "BEFORE UPDATE OR DELETE ON public.artifact_versions FOR EACH ROW "
        "EXECUTE FUNCTION public.protect_artifact_version()"
    )

    for table_name in ("artifacts", "artifact_versions"):
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM PUBLIC")
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
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.artifact_versions)
                OR EXISTS (SELECT 1 FROM public.artifacts)
            THEN
                RAISE EXCEPTION 'cannot downgrade while Artifacts exist'
                    USING ERRCODE = '55000';
            END IF;
        END
        $aria$
        """
    )
    op.execute("DROP TRIGGER trg_artifact_versions_protect ON public.artifact_versions")
    op.execute("DROP FUNCTION public.protect_artifact_version()")
    op.execute("DROP TRIGGER trg_artifacts_set_updated_at ON public.artifacts")
    op.execute("DROP TRIGGER trg_artifacts_protect_lifecycle ON public.artifacts")
    op.execute("DROP FUNCTION public.protect_artifact_lifecycle()")
    op.drop_constraint(
        "fk_artifacts_current_version_tenant", "artifacts", type_="foreignkey"
    )
    op.drop_index("ix_artifact_versions_artifact_version", table_name="artifact_versions")
    op.drop_index(
        "ix_artifact_versions_account_project_created", table_name="artifact_versions"
    )
    op.drop_index("ix_artifacts_account_project", table_name="artifacts")
    op.drop_table("artifact_versions")
    op.drop_table("artifacts")
