"""Allow AI-02/AI-03 to lock only their pinned rows as aria_worker."""

from alembic import op

revision: str = "0030_generation_input_row_locks"
down_revision: str | None = "0029_scope_generation_runtime"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $aria$
        DECLARE
            v_role record;
        BEGIN
            SELECT
                rolcanlogin,
                rolinherit,
                rolsuper,
                rolcreatedb,
                rolcreaterole,
                rolreplication,
                rolbypassrls
            INTO v_role
            FROM pg_catalog.pg_roles
            WHERE rolname='aria_generation_lock_owner';

            IF NOT FOUND THEN
                EXECUTE
                    'CREATE ROLE aria_generation_lock_owner '
                    'NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS';
            ELSIF v_role.rolcanlogin
               OR v_role.rolinherit
               OR v_role.rolsuper
               OR v_role.rolcreatedb
               OR v_role.rolcreaterole
               OR v_role.rolreplication
               OR v_role.rolbypassrls THEN
                RAISE EXCEPTION
                    'generation lock owner role attributes rejected'
                    USING ERRCODE = '42501';
            END IF;
        END
        $aria$
        """
    )
    op.execute("CREATE SCHEMA aria_internal")
    op.execute("REVOKE ALL ON SCHEMA aria_internal FROM PUBLIC")
    op.execute("GRANT USAGE, CREATE ON SCHEMA aria_internal TO aria_generation_lock_owner")
    op.execute("GRANT USAGE ON SCHEMA aria_internal TO aria_worker")
    op.execute("GRANT USAGE ON SCHEMA public TO aria_generation_lock_owner")
    op.execute(
        "GRANT SELECT (id, account_id, project_id, job_type, status, payload_ref) "
        "ON public.jobs TO aria_generation_lock_owner"
    )
    op.execute(
        "GRANT SELECT (id, account_id, current_context_version, deleted_at) "
        "ON public.projects TO aria_generation_lock_owner"
    )
    for relation in ("context_items", "requirements"):
        op.execute(
            "GRANT SELECT (id, account_id, project_id, context_version, status), "
            f"UPDATE (id) ON public.{relation} TO aria_generation_lock_owner"
        )
    for relation in ("jobs", "projects", "context_items", "requirements"):
        op.execute(
            f"CREATE POLICY {relation}_generation_lock_owner_select "
            f"ON public.{relation} FOR SELECT TO aria_generation_lock_owner "
            "USING (account_id::text = "
            "pg_catalog.current_setting('aria.lock_account_id', true))"
        )
    for relation in ("context_items", "requirements"):
        op.execute(
            f"CREATE POLICY {relation}_generation_lock_owner_update "
            f"ON public.{relation} FOR UPDATE TO aria_generation_lock_owner "
            "USING (account_id::text = "
            "pg_catalog.current_setting('aria.lock_account_id', true)) "
            "WITH CHECK (account_id::text = "
            "pg_catalog.current_setting('aria.lock_account_id', true))"
        )

    for workflow, lock_requirements in (
        ("requirement_generation", False),
        ("gap_detection", True),
    ):
        function_name = (
            "lock_requirement_generation_inputs"
            if workflow == "requirement_generation"
            else "lock_gap_detection_inputs"
        )
        requirement_lock = (
            """
            PERFORM id FROM public.requirements
            WHERE account_id=p_account_id AND project_id=p_project_id
              AND context_version=p_context_version
              AND status IN ('draft', 'confirmed')
            ORDER BY id FOR SHARE;
            """
            if lock_requirements
            else ""
        )
        op.execute(
            f"""
            CREATE FUNCTION aria_internal.{function_name}(
                p_job_id uuid, p_account_id uuid, p_project_id uuid,
                p_context_version integer
            ) RETURNS void
            LANGUAGE plpgsql VOLATILE SECURITY DEFINER
            SET search_path = ''
            AS $aria$
            BEGIN
                IF p_job_id IS NULL OR p_account_id IS NULL
                   OR p_project_id IS NULL OR p_context_version IS NULL
                   OR p_context_version < 1 THEN
                    RAISE EXCEPTION 'generation input lock scope rejected'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM pg_catalog.set_config(
                    'aria.lock_account_id', p_account_id::text, true
                );
                PERFORM 1 FROM public.jobs
                WHERE id=p_job_id AND account_id=p_account_id
                  AND project_id=p_project_id
                  AND job_type='{workflow}' AND status='running'
                  AND payload_ref->>'context_version'=p_context_version::text;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'generation input lock scope rejected'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM 1 FROM public.projects
                WHERE id=p_project_id AND account_id=p_account_id
                  AND deleted_at IS NULL
                  AND current_context_version>=p_context_version;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'generation input lock scope rejected'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM id FROM public.context_items
                WHERE account_id=p_account_id AND project_id=p_project_id
                  AND context_version=p_context_version
                  AND status IN ('proposed', 'confirmed')
                ORDER BY id FOR SHARE;
                {requirement_lock}
            END
            $aria$
            """
        )
        op.execute(
            "REVOKE ALL ON FUNCTION "
            f"aria_internal.{function_name}(uuid, uuid, uuid, integer) FROM PUBLIC"
        )
        op.execute(
            "ALTER FUNCTION "
            f"aria_internal.{function_name}(uuid, uuid, uuid, integer) "
            "OWNER TO aria_generation_lock_owner"
        )
        op.execute(
            "GRANT EXECUTE ON FUNCTION "
            f"aria_internal.{function_name}(uuid, uuid, uuid, integer) TO aria_worker"
        )
        op.execute(
            f"""
            DO $aria$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_proc p
                    JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
                    CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) acl
                    WHERE n.nspname='aria_internal'
                      AND p.proname='{function_name}'
                      AND acl.privilege_type='EXECUTE'
                      AND acl.grantee NOT IN (
                          p.proowner,
                          (SELECT oid FROM pg_catalog.pg_roles
                           WHERE rolname='aria_worker')
                      )
                ) THEN
                    RAISE EXCEPTION 'generation lock helper has unexpected execute grant';
                END IF;
            END
            $aria$
            """
        )


def downgrade() -> None:
    for function_name in (
        "lock_gap_detection_inputs",
        "lock_requirement_generation_inputs",
    ):
        op.execute(
            "REVOKE EXECUTE ON FUNCTION "
            f"aria_internal.{function_name}(uuid, uuid, uuid, integer) FROM aria_worker"
        )
        op.execute(
            "DROP FUNCTION aria_internal."
            f"{function_name}(uuid, uuid, uuid, integer)"
        )
    for relation in ("requirements", "context_items"):
        op.execute(
            f"DROP POLICY {relation}_generation_lock_owner_update ON public.{relation}"
        )
    for relation in ("requirements", "context_items", "projects", "jobs"):
        op.execute(
            f"DROP POLICY {relation}_generation_lock_owner_select ON public.{relation}"
        )
    for relation in ("context_items", "requirements"):
        op.execute(
            f"REVOKE SELECT, UPDATE ON public.{relation} FROM aria_generation_lock_owner"
        )
    op.execute(
        "REVOKE SELECT ON public.projects, public.jobs FROM aria_generation_lock_owner"
    )
    op.execute("REVOKE USAGE ON SCHEMA aria_internal FROM aria_worker")
    op.execute("REVOKE USAGE ON SCHEMA public FROM aria_generation_lock_owner")
    op.execute(
        "REVOKE USAGE, CREATE ON SCHEMA aria_internal FROM aria_generation_lock_owner"
    )
    op.execute("DROP SCHEMA aria_internal")
    op.execute(
        """
        DO $aria$
        DECLARE
            v_role_oid oid;
            v_current_database_oid oid;
        BEGIN
            SELECT oid INTO v_role_oid
            FROM pg_catalog.pg_roles
            WHERE rolname='aria_generation_lock_owner';
            IF NOT FOUND THEN
                RETURN;
            END IF;

            SELECT oid INTO STRICT v_current_database_oid
            FROM pg_catalog.pg_database
            WHERE datname=pg_catalog.current_database();

            IF EXISTS (
                SELECT 1
                FROM pg_catalog.pg_shdepend
                WHERE refclassid='pg_catalog.pg_authid'::pg_catalog.regclass
                  AND refobjid=v_role_oid
                  AND dbid <> v_current_database_oid
            ) THEN
                RAISE NOTICE
                    'preserving aria_generation_lock_owner: used outside current database';
            ELSE
                EXECUTE 'DROP ROLE aria_generation_lock_owner';
            END IF;
        END
        $aria$
        """
    )
