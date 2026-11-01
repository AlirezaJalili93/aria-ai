"""Add the synthetic Artifact Generation checkpoint and limited Worker helper."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039_artifact_generation_runtime"
down_revision: str | None = "0038_artifact_version_foundation"
branch_labels: str | None = None
depends_on: str | None = None


_HELPER_FUNCTIONS = (
    "release_artifact_generation(uuid, uuid)",
    "finalize_artifact_generation(uuid, uuid, text, text)",
    "save_artifact_generation_checkpoint(uuid, uuid, text, text)",
    "claim_artifact_generation(uuid, uuid)",
    "resolve_artifact_generation_binding(uuid, uuid)",
)


def upgrade() -> None:
    op.add_column("artifact_versions", sa.Column("checkpoint_ref", sa.Text(), nullable=True))
    op.add_column(
        "artifact_versions", sa.Column("checkpoint_hash", sa.String(length=71), nullable=True)
    )
    op.create_check_constraint(
        "artifact_version_checkpoint_hash",
        "artifact_versions",
        "checkpoint_hash IS NULL OR checkpoint_hash ~ '^sha256:[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "artifact_version_checkpoint_pair",
        "artifact_versions",
        "(checkpoint_ref IS NULL AND checkpoint_hash IS NULL) OR "
        "(checkpoint_ref IS NOT NULL AND length(btrim(checkpoint_ref)) > 0 "
        "AND checkpoint_hash IS NOT NULL)",
    )
    op.create_index(
        "uq_artifact_versions_one_active_generation",
        "artifact_versions",
        ["artifact_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','generating','validating')"),
    )

    op.create_table(
        "artifact_generation_claims",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outbox_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_backend_pid", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["public.jobs.id"], ondelete="CASCADE",
            name="fk_artifact_generation_claims_job",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_event_id"], ["public.outbox_events.id"], ondelete="CASCADE",
            name="fk_artifact_generation_claims_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"], ["public.artifact_versions.id"], ondelete="CASCADE",
            name="fk_artifact_generation_claims_version",
        ),
        sa.PrimaryKeyConstraint("job_id", name="pk_artifact_generation_claims"),
        sa.UniqueConstraint(
            "outbox_event_id", name="uq_artifact_generation_claims_outbox"
        ),
        schema="aria_internal",
    )
    op.execute(
        "REVOKE ALL ON TABLE aria_internal.artifact_generation_claims FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON TABLE aria_internal.artifact_generation_claims FROM aria_worker"
    )

    op.execute(
        """
        DO $aria$
        DECLARE v_role record;
        BEGIN
            SELECT rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole,
                   rolreplication, rolbypassrls
            INTO v_role
            FROM pg_catalog.pg_roles
            WHERE rolname='aria_artifact_runtime_owner';

            IF NOT FOUND THEN
                EXECUTE 'CREATE ROLE aria_artifact_runtime_owner '
                        'NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                        'NOCREATEROLE NOREPLICATION NOBYPASSRLS';
            ELSIF v_role.rolcanlogin OR v_role.rolinherit OR v_role.rolsuper
               OR v_role.rolcreatedb OR v_role.rolcreaterole
               OR v_role.rolreplication OR v_role.rolbypassrls THEN
                RAISE EXCEPTION 'artifact runtime owner role attributes rejected'
                    USING ERRCODE='42501';
            END IF;
        END
        $aria$
        """
    )
    op.execute(
        "ALTER TABLE aria_internal.artifact_generation_claims "
        "OWNER TO aria_artifact_runtime_owner"
    )
    op.execute("GRANT USAGE ON SCHEMA aria_internal TO aria_artifact_runtime_owner")
    op.execute("GRANT USAGE ON SCHEMA aria_internal TO aria_worker")
    op.execute("GRANT USAGE ON SCHEMA public TO aria_artifact_runtime_owner")

    grants = {
        "jobs": "id, account_id, project_id, job_type, status, payload_ref, attempt_count, "
        "max_attempts, correlation_id, started_at, finished_at, error_code, error_detail",
        "outbox_events": "id, account_id, aggregate_type, aggregate_id, event_type, "
        "delivery_channel, payload, status",
        "projects": "id, account_id, project_type, deleted_at",
        "scope_versions": "id, account_id, project_id, version_no, snapshot_hash, status",
        "artifacts": "id, account_id, project_id, current_version_id, status",
        "artifact_versions": "id, account_id, project_id, artifact_id, scope_version_id, "
        "version_no, generation_job_id, status, checkpoint_ref, checkpoint_hash, "
        "storage_ref, artifact_hash",
    }
    for relation, columns in grants.items():
        op.execute(
            f"GRANT SELECT ({columns}) ON public.{relation} "
            "TO aria_artifact_runtime_owner"
        )
        op.execute(
            f"CREATE POLICY {relation}_artifact_runtime_owner_select "
            f"ON public.{relation} FOR SELECT TO aria_artifact_runtime_owner USING (true)"
        )
    op.execute(
        "GRANT UPDATE (status, attempt_count, started_at, finished_at, error_code, error_detail) "
        "ON public.jobs TO aria_artifact_runtime_owner"
    )
    op.execute(
        "GRANT UPDATE (status, checkpoint_ref, checkpoint_hash, storage_ref, artifact_hash) "
        "ON public.artifact_versions TO aria_artifact_runtime_owner"
    )
    op.execute(
        "GRANT UPDATE (current_version_id, status, updated_at) "
        "ON public.artifacts TO aria_artifact_runtime_owner"
    )
    for relation in ("jobs", "artifact_versions", "artifacts"):
        op.execute(
            f"CREATE POLICY {relation}_artifact_runtime_owner_update "
            f"ON public.{relation} FOR UPDATE TO aria_artifact_runtime_owner "
            "USING (true) WITH CHECK (true)"
        )

    op.execute(
        """
        CREATE FUNCTION aria_internal.resolve_artifact_generation_binding(
            p_job_id uuid, p_outbox_event_id uuid
        ) RETURNS jsonb
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path=''
        AS $aria$
        DECLARE v_result jsonb;
        BEGIN
            IF p_job_id IS NULL OR p_outbox_event_id IS NULL THEN
                RAISE EXCEPTION 'artifact generation identity rejected'
                    USING ERRCODE='42501';
            END IF;
            SELECT pg_catalog.jsonb_build_object(
                'job_id', j.id,
                'account_id', j.account_id,
                'project_id', j.project_id,
                'correlation_id', j.correlation_id,
                'job_status', j.status,
                'artifact_id', av.artifact_id,
                'artifact_version_id', av.id,
                'artifact_version_status', av.status,
                'version_no', av.version_no,
                'scope_version_id', sv.id,
                'scope_version_no', sv.version_no,
                'scope_version_hash', sv.snapshot_hash,
                'project_type', p.project_type,
                'checkpoint_ref', av.checkpoint_ref,
                'checkpoint_hash', av.checkpoint_hash,
                'current_version_id', a.current_version_id
            ) INTO v_result
            FROM public.jobs AS j
            JOIN public.artifact_versions AS av
              ON av.generation_job_id=j.id
             AND av.account_id=j.account_id
             AND av.project_id=j.project_id
            JOIN public.artifacts AS a
              ON a.id=av.artifact_id
             AND a.account_id=av.account_id
             AND a.project_id=av.project_id
            JOIN public.scope_versions AS sv
              ON sv.id=av.scope_version_id
             AND sv.account_id=av.account_id
             AND sv.project_id=av.project_id
            JOIN public.projects AS p
              ON p.id=j.project_id AND p.account_id=j.account_id
            JOIN public.outbox_events AS oe
              ON oe.id=p_outbox_event_id
             AND oe.account_id=j.account_id
            WHERE j.id=p_job_id
              AND j.job_type='artifact_generation'
              AND j.status IN ('queued','running','succeeded')
              AND j.payload_ref=pg_catalog.jsonb_build_object(
                    'artifact_version_id', av.id::text,
                    'scope_version_id', sv.id::text
                  )
              AND oe.aggregate_type='artifact_version'
              AND oe.aggregate_id=av.id
              AND oe.event_type='artifact.generation_requested.v1'
              AND oe.delivery_channel='job_queue'
              AND oe.payload=pg_catalog.jsonb_build_object(
                    'jobId', j.id::text,
                    'taskType', 'artifact_generation',
                    'payloadVersion', '1'
                  )
              AND p.deleted_at IS NULL
              AND sv.status='approved';
            IF v_result IS NULL THEN
                RAISE EXCEPTION 'artifact generation binding rejected'
                    USING ERRCODE='42501';
            END IF;
            RETURN v_result;
        END
        $aria$
        """
    )
    op.execute(
        """
        CREATE FUNCTION aria_internal.claim_artifact_generation(
            p_job_id uuid, p_outbox_event_id uuid
        ) RETURNS jsonb
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=''
        AS $aria$
        DECLARE
            v_lock_key bigint := pg_catalog.hashtextextended(
                'aria:artifact-generation:' || p_job_id::text, 0
            );
            v_binding jsonb;
            v_job_status text;
            v_version_status text;
        BEGIN
            IF NOT pg_catalog.pg_try_advisory_lock(v_lock_key) THEN
                RAISE EXCEPTION 'artifact generation already owned'
                    USING ERRCODE='55P03';
            END IF;
            BEGIN
                PERFORM 1 FROM public.jobs WHERE id=p_job_id FOR UPDATE;
                v_binding := aria_internal.resolve_artifact_generation_binding(
                    p_job_id, p_outbox_event_id
                );
                v_job_status := v_binding->>'job_status';
                v_version_status := v_binding->>'artifact_version_status';

                IF v_job_status='succeeded' AND v_version_status='ready'
                   AND v_binding->>'current_version_id'=
                       v_binding->>'artifact_version_id' THEN
                    PERFORM pg_catalog.pg_advisory_unlock(v_lock_key);
                    RETURN v_binding || pg_catalog.jsonb_build_object(
                        'already_completed', true
                    );
                END IF;
                IF v_job_status NOT IN ('queued','running')
                   OR v_version_status NOT IN ('queued','generating','validating') THEN
                    RAISE EXCEPTION 'artifact generation state rejected'
                        USING ERRCODE='42501';
                END IF;

                INSERT INTO aria_internal.artifact_generation_claims(
                    job_id, outbox_event_id, artifact_version_id,
                    owner_backend_pid, claimed_at
                ) VALUES (
                    p_job_id, p_outbox_event_id,
                    (v_binding->>'artifact_version_id')::uuid,
                    pg_catalog.pg_backend_pid(), CURRENT_TIMESTAMP
                )
                ON CONFLICT (job_id) DO UPDATE
                SET outbox_event_id=EXCLUDED.outbox_event_id,
                    artifact_version_id=EXCLUDED.artifact_version_id,
                    owner_backend_pid=EXCLUDED.owner_backend_pid,
                    claimed_at=EXCLUDED.claimed_at;

                UPDATE public.jobs
                SET status='running',
                    attempt_count=CASE WHEN status='queued' THEN 1 ELSE attempt_count END,
                    started_at=COALESCE(started_at, CURRENT_TIMESTAMP),
                    finished_at=NULL, error_code=NULL, error_detail=NULL
                WHERE id=p_job_id AND status IN ('queued','running');
                UPDATE public.artifact_versions
                SET status=CASE WHEN status='queued' THEN 'generating' ELSE status END
                WHERE id=(v_binding->>'artifact_version_id')::uuid
                  AND status IN ('queued','generating','validating');
                RETURN aria_internal.resolve_artifact_generation_binding(
                    p_job_id, p_outbox_event_id
                ) || pg_catalog.jsonb_build_object('already_completed', false);
            EXCEPTION WHEN OTHERS THEN
                PERFORM pg_catalog.pg_advisory_unlock(v_lock_key);
                RAISE;
            END;
        END
        $aria$
        """
    )
    op.execute(
        """
        CREATE FUNCTION aria_internal.save_artifact_generation_checkpoint(
            p_job_id uuid, p_outbox_event_id uuid,
            p_checkpoint_ref text, p_checkpoint_hash text
        ) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=''
        AS $aria$
        DECLARE v_binding jsonb; v_prefix text;
        BEGIN
            v_binding := aria_internal.resolve_artifact_generation_binding(
                p_job_id, p_outbox_event_id
            );
            PERFORM 1 FROM aria_internal.artifact_generation_claims
            WHERE job_id=p_job_id AND outbox_event_id=p_outbox_event_id
              AND artifact_version_id=(v_binding->>'artifact_version_id')::uuid
              AND owner_backend_pid=pg_catalog.pg_backend_pid();
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact generation ownership rejected'
                    USING ERRCODE='42501';
            END IF;
            v_prefix := 'artifacts/' || (v_binding->>'account_id') || '/'
                || (v_binding->>'project_id') || '/' || (v_binding->>'artifact_id')
                || '/versions/' || (v_binding->>'artifact_version_id');
            IF p_checkpoint_ref IS NULL
               OR p_checkpoint_ref<>v_prefix || '/checkpoint/build-bundle.tar'
               OR p_checkpoint_hash IS NULL
               OR p_checkpoint_hash !~ '^sha256:[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'artifact checkpoint rejected' USING ERRCODE='23514';
            END IF;
            PERFORM 1 FROM public.jobs WHERE id=p_job_id AND status='running' FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact generation state rejected' USING ERRCODE='42501';
            END IF;
            PERFORM 1 FROM public.artifact_versions
            WHERE id=(v_binding->>'artifact_version_id')::uuid
              AND status IN ('generating','validating') FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact version state rejected' USING ERRCODE='42501';
            END IF;
            UPDATE public.artifact_versions
            SET checkpoint_ref=p_checkpoint_ref,
                checkpoint_hash=p_checkpoint_hash,
                status='validating'
            WHERE id=(v_binding->>'artifact_version_id')::uuid
              AND (
                (checkpoint_ref IS NULL AND checkpoint_hash IS NULL)
                OR (checkpoint_ref=p_checkpoint_ref AND checkpoint_hash=p_checkpoint_hash)
              );
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact checkpoint conflict' USING ERRCODE='23514';
            END IF;
        END
        $aria$
        """
    )
    op.execute(
        """
        CREATE FUNCTION aria_internal.finalize_artifact_generation(
            p_job_id uuid, p_outbox_event_id uuid,
            p_storage_ref text, p_artifact_hash text
        ) RETURNS text
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=''
        AS $aria$
        DECLARE
            v_binding jsonb;
            v_prefix text;
            v_current_version_no integer;
        BEGIN
            v_binding := aria_internal.resolve_artifact_generation_binding(
                p_job_id, p_outbox_event_id
            );
            PERFORM 1 FROM aria_internal.artifact_generation_claims
            WHERE job_id=p_job_id AND outbox_event_id=p_outbox_event_id
              AND artifact_version_id=(v_binding->>'artifact_version_id')::uuid
              AND owner_backend_pid=pg_catalog.pg_backend_pid();
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact generation ownership rejected'
                    USING ERRCODE='42501';
            END IF;
            v_prefix := 'artifacts/' || (v_binding->>'account_id') || '/'
                || (v_binding->>'project_id') || '/' || (v_binding->>'artifact_id')
                || '/versions/' || (v_binding->>'artifact_version_id');
            IF p_storage_ref IS NULL OR p_storage_ref<>v_prefix || '/manifest.json'
               OR p_artifact_hash IS NULL
               OR p_artifact_hash !~ '^sha256:[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'artifact finalization payload rejected'
                    USING ERRCODE='23514';
            END IF;
            PERFORM 1 FROM public.jobs WHERE id=p_job_id AND status='running' FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact generation state rejected' USING ERRCODE='42501';
            END IF;
            PERFORM 1 FROM public.artifact_versions
            WHERE id=(v_binding->>'artifact_version_id')::uuid
              AND status='validating'
              AND checkpoint_ref IS NOT NULL AND checkpoint_hash IS NOT NULL
            FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'artifact checkpoint state rejected' USING ERRCODE='42501';
            END IF;
            PERFORM 1 FROM public.artifacts
            WHERE id=(v_binding->>'artifact_id')::uuid FOR UPDATE;

            IF (v_binding->>'current_version_id') IS NOT NULL THEN
                SELECT version_no INTO v_current_version_no
                FROM public.artifact_versions
                WHERE id=(v_binding->>'current_version_id')::uuid;
            END IF;
            IF v_current_version_no IS NOT NULL
               AND v_current_version_no >= (v_binding->>'version_no')::integer THEN
                UPDATE public.artifact_versions
                SET status='failed'
                WHERE id=(v_binding->>'artifact_version_id')::uuid;
                UPDATE public.jobs
                SET status='failed', finished_at=CURRENT_TIMESTAMP,
                    error_code='ARTIFACT_GENERATION_STALE', error_detail=NULL
                WHERE id=p_job_id;
                DELETE FROM aria_internal.artifact_generation_claims
                WHERE job_id=p_job_id AND owner_backend_pid=pg_catalog.pg_backend_pid();
                RETURN 'stale';
            END IF;

            UPDATE public.artifact_versions
            SET storage_ref=p_storage_ref, artifact_hash=p_artifact_hash, status='ready'
            WHERE id=(v_binding->>'artifact_version_id')::uuid;
            UPDATE public.artifacts
            SET current_version_id=(v_binding->>'artifact_version_id')::uuid,
                status='ready'
            WHERE id=(v_binding->>'artifact_id')::uuid;
            UPDATE public.jobs
            SET status='succeeded', finished_at=CURRENT_TIMESTAMP,
                error_code=NULL, error_detail=NULL
            WHERE id=p_job_id;
            DELETE FROM aria_internal.artifact_generation_claims
            WHERE job_id=p_job_id AND owner_backend_pid=pg_catalog.pg_backend_pid();
            RETURN 'finalized';
        END
        $aria$
        """
    )
    op.execute(
        """
        CREATE FUNCTION aria_internal.release_artifact_generation(
            p_job_id uuid, p_outbox_event_id uuid
        ) RETURNS void
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=''
        AS $aria$
        DECLARE v_lock_key bigint := pg_catalog.hashtextextended(
            'aria:artifact-generation:' || p_job_id::text, 0
        );
        BEGIN
            DELETE FROM aria_internal.artifact_generation_claims
            WHERE job_id=p_job_id AND outbox_event_id=p_outbox_event_id
              AND owner_backend_pid=pg_catalog.pg_backend_pid();
            PERFORM pg_catalog.pg_advisory_unlock(v_lock_key);
        END
        $aria$
        """
    )

    for signature in _HELPER_FUNCTIONS:
        op.execute(
            f"REVOKE ALL ON FUNCTION aria_internal.{signature} FROM PUBLIC"
        )
        op.execute(
            f"ALTER FUNCTION aria_internal.{signature} OWNER TO aria_artifact_runtime_owner"
        )
    for signature in _HELPER_FUNCTIONS[:-1]:
        # The binding resolver is private to the operation-specific helpers.
        if not signature.startswith("resolve_"):
            op.execute(
                f"GRANT EXECUTE ON FUNCTION aria_internal.{signature} TO aria_worker"
            )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.protect_artifact_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path=''
        AS $aria$
        DECLARE target_status text; target_version_no integer; current_version_no integer;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'artifacts cannot be deleted' USING ERRCODE='55000';
            END IF;
            IF (NEW.id, NEW.account_id, NEW.project_id, NEW.artifact_type, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.account_id, OLD.project_id, OLD.artifact_type, OLD.created_at)
            THEN
                RAISE EXCEPTION 'artifact identity is immutable' USING ERRCODE='55000';
            END IF;
            IF NEW.current_version_id IS DISTINCT FROM OLD.current_version_id
               AND NEW.current_version_id IS NOT NULL THEN
                SELECT av.status, av.version_no INTO target_status, target_version_no
                FROM public.artifact_versions AS av
                WHERE av.id=NEW.current_version_id AND av.artifact_id=NEW.id
                  AND av.account_id=NEW.account_id AND av.project_id=NEW.project_id;
                IF target_status IS DISTINCT FROM 'ready' THEN
                    RAISE EXCEPTION 'artifact current version must be ready and owned'
                        USING ERRCODE='23514';
                END IF;
                IF OLD.current_version_id IS NOT NULL THEN
                    SELECT av.version_no INTO current_version_no
                    FROM public.artifact_versions AS av
                    WHERE av.id=OLD.current_version_id;
                    IF target_version_no<=current_version_no THEN
                        RAISE EXCEPTION 'artifact current version must move forward'
                            USING ERRCODE='23514';
                    END IF;
                END IF;
            END IF;
            IF OLD.current_version_id IS NOT NULL AND NEW.current_version_id IS NULL THEN
                RAISE EXCEPTION 'artifact current version cannot be cleared'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $aria$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.artifact_versions
                WHERE checkpoint_ref IS NOT NULL OR checkpoint_hash IS NOT NULL
                   OR status IN ('generating','validating')
            ) THEN
                RAISE EXCEPTION 'cannot downgrade with Artifact runtime state'
                    USING ERRCODE='55000';
            END IF;
        END
        $aria$
        """
    )
    for signature in _HELPER_FUNCTIONS:
        op.execute(f"DROP FUNCTION aria_internal.{signature}")
    for relation in ("artifacts", "artifact_versions", "jobs"):
        op.execute(
            f"DROP POLICY {relation}_artifact_runtime_owner_update ON public.{relation}"
        )
    for relation in (
        "artifact_versions", "artifacts", "scope_versions", "projects",
        "outbox_events", "jobs",
    ):
        op.execute(
            f"DROP POLICY {relation}_artifact_runtime_owner_select ON public.{relation}"
        )
    op.execute("REVOKE ALL ON public.artifacts FROM aria_artifact_runtime_owner")
    op.execute("REVOKE ALL ON public.artifact_versions FROM aria_artifact_runtime_owner")
    op.execute("REVOKE ALL ON public.scope_versions FROM aria_artifact_runtime_owner")
    op.execute("REVOKE ALL ON public.projects FROM aria_artifact_runtime_owner")
    op.execute("REVOKE ALL ON public.outbox_events FROM aria_artifact_runtime_owner")
    op.execute("REVOKE ALL ON public.jobs FROM aria_artifact_runtime_owner")
    op.drop_table("artifact_generation_claims", schema="aria_internal")
    op.execute("REVOKE USAGE ON SCHEMA public FROM aria_artifact_runtime_owner")
    op.execute("REVOKE USAGE ON SCHEMA aria_internal FROM aria_artifact_runtime_owner")
    op.execute("DROP ROLE aria_artifact_runtime_owner")
    op.drop_index(
        "uq_artifact_versions_one_active_generation",
        table_name="artifact_versions",
    )
    op.drop_constraint(
        "artifact_version_checkpoint_pair", "artifact_versions", type_="check"
    )
    op.drop_constraint(
        "artifact_version_checkpoint_hash", "artifact_versions", type_="check"
    )
    op.drop_column("artifact_versions", "checkpoint_hash")
    op.drop_column("artifact_versions", "checkpoint_ref")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.protect_artifact_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path=''
        AS $aria$
        DECLARE target_status text;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'artifacts cannot be deleted' USING ERRCODE='55000';
            END IF;
            IF (NEW.id, NEW.account_id, NEW.project_id, NEW.artifact_type, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.account_id, OLD.project_id, OLD.artifact_type, OLD.created_at)
            THEN
                RAISE EXCEPTION 'artifact identity is immutable' USING ERRCODE='55000';
            END IF;
            IF NEW.current_version_id IS DISTINCT FROM OLD.current_version_id
               AND NEW.current_version_id IS NOT NULL THEN
                SELECT av.status INTO target_status
                FROM public.artifact_versions AS av
                WHERE av.id=NEW.current_version_id AND av.artifact_id=NEW.id
                  AND av.account_id=NEW.account_id AND av.project_id=NEW.project_id;
                IF target_status IS DISTINCT FROM 'ready' THEN
                    RAISE EXCEPTION 'artifact current version must be ready and owned'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            IF OLD.current_version_id IS NOT NULL AND NEW.current_version_id IS NULL THEN
                RAISE EXCEPTION 'artifact current version cannot be cleared'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END
        $aria$
        """
    )
