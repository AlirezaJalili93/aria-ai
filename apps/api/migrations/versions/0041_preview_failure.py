"""Approved owned-session Preview failure helper; Local/Synthetic verification only."""

from alembic import op

revision: str = "0041_preview_failure"
down_revision: str | None = "0040_preview_publication"
branch_labels: str | None = None
depends_on: str | None = None

# Literal owner-reviewed SQL, embedded without a docs runtime dependency.
_STATEMENTS: tuple[str, ...] = (
    r"""
GRANT SELECT (error_code) ON public.jobs TO aria_preview_runtime_owner;
""",
    r"""
CREATE FUNCTION aria_internal.fail_preview(p_job UUID, p_event UUID, p_error TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $body$
DECLARE b RECORD; k BIGINT;
BEGIN
    IF p_job IS NULL OR p_event IS NULL OR p_error IS NULL
        OR p_error NOT IN ('PREVIEW_SOURCE_UNSUPPORTED', 'PREVIEW_SOURCE_INVALID',
                          'PREVIEW_DELIVERY_CONFLICT') THEN
        RAISE EXCEPTION 'Preview failure denied' USING ERRCODE = '42501';
    END IF;

    -- Same fixed lock order as the accepted claim/finalize helpers.
    PERFORM j.id FROM public.jobs AS j
        WHERE j.id = p_job AND j.job_type = 'preview_publication' FOR UPDATE;
    PERFORM p.id FROM public.preview_publications AS p
        WHERE p.publish_job_id = p_job FOR UPDATE;
    PERFORM r.id FROM public.preview_representations AS r
        JOIN public.preview_publications AS p ON p.representation_id = r.id
        WHERE p.publish_job_id = p_job FOR UPDATE OF r;

    SELECT j.id AS job_id, j.account_id, j.project_id,
        j.status AS job_status, j.error_code AS job_error
    INTO b
    FROM aria_internal.preview_execution_claims AS c
    JOIN public.jobs AS j ON j.id = c.job_id
        AND j.job_type = 'preview_publication' AND j.status IN ('running', 'failed')
    JOIN public.preview_publications AS p ON p.publish_job_id = j.id
        AND (p.account_id, p.project_id) = (j.account_id, j.project_id)
    JOIN public.preview_representations AS r ON
        (r.id, r.artifact_version_id, r.account_id, r.project_id) =
        (p.representation_id, p.artifact_version_id, p.account_id, p.project_id)
    JOIN public.artifact_versions AS a ON
        (a.id, a.artifact_id, a.account_id, a.project_id) =
        (r.artifact_version_id, r.artifact_id, r.account_id, r.project_id)
    JOIN public.artifacts AS ar ON
        (ar.id, ar.account_id, ar.project_id) = (a.artifact_id, a.account_id, a.project_id)
    JOIN public.projects AS pr ON (pr.id, pr.account_id) = (ar.project_id, ar.account_id)
    JOIN public.accounts AS ac ON ac.id = pr.account_id
    JOIN public.outbox_events AS e ON e.id = c.outbox_event_id AND e.id = p_event
        AND e.account_id = j.account_id AND e.aggregate_type = 'job' AND e.aggregate_id = j.id
        AND e.event_type = 'preview.publication_requested.v1' AND e.delivery_channel = 'job_queue'
        AND e.payload = pg_catalog.jsonb_build_object('jobId', j.id::TEXT,
            'taskType', 'preview_publication', 'payloadVersion', '1')
    WHERE c.job_id = p_job AND c.owner_backend_pid = pg_catalog.pg_backend_pid()
        AND j.payload_ref = pg_catalog.jsonb_build_object('publication_id', p.id::TEXT,
            'representation_id', r.id::TEXT, 'artifact_version_id', a.id::TEXT)
        AND p.status = 'publishing' AND p.revoked_at IS NULL AND p.token_hash IS NULL
        AND r.status IN ('preparing', 'ready')
        AND a.status = 'ready' AND a.artifact_hash = r.source_hash
        AND r.transformer_version = 'preview_delivery_transformer_v1'
        AND r.delivery_policy_version = 'preview_delivery_policy_v1';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Preview failure binding denied' USING ERRCODE = '42501';
    END IF;

    -- A stale PID/claim row is not sufficient: require this backend's live advisory lock.
    -- This only inspects ownership; it never acquires, increments or unlocks the lock.
    k := pg_catalog.hashtextextended('aria:preview:' || p_job::TEXT, 0);
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_locks AS l
        WHERE l.locktype = 'advisory' AND l.pid = pg_catalog.pg_backend_pid()
            AND l.granted AND l.mode = 'ExclusiveLock' AND l.objsubid = 1
            AND l.database = (SELECT d.oid FROM pg_catalog.pg_database AS d
                WHERE d.datname = pg_catalog.current_database())
            AND l.classid = ((k >> 32) & 4294967295)::OID
            AND l.objid = (k & 4294967295)::OID
    ) THEN
        RAISE EXCEPTION 'Preview failure ownership denied' USING ERRCODE = '42501';
    END IF;

    -- Same-session persistence replay preserves the original terminal reason and timestamp.
    IF b.job_status = 'failed' THEN
        IF b.job_error IS NOT DISTINCT FROM p_error THEN
            RETURN;
        END IF;
        RAISE EXCEPTION 'Preview terminal failure conflict' USING ERRCODE = '42501';
    END IF;
    UPDATE public.jobs SET status = 'failed', finished_at = pg_catalog.clock_timestamp(),
        error_code = p_error, error_detail = NULL
        WHERE id = b.job_id AND account_id = b.account_id AND project_id = b.project_id
            AND job_type = 'preview_publication' AND status = 'running';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Preview failure transition denied' USING ERRCODE = '42501';
    END IF;
    -- Keep the exact claim until caller commits, then uses the existing release helper.
    -- No Publication/Representation/Artifact/File/capability mutation or deletion occurs.
END;
$body$;
""",
    r"""
REVOKE ALL ON FUNCTION aria_internal.fail_preview(UUID, UUID, TEXT) FROM PUBLIC;
""",
    r"""
DO $acl$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION aria_internal.fail_preview(UUID, UUID, TEXT) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION aria_internal.fail_preview(UUID, UUID, TEXT) FROM authenticated;
    END IF;
END;
$acl$;
""",
    r"""
ALTER FUNCTION aria_internal.fail_preview(UUID, UUID, TEXT) OWNER TO aria_preview_runtime_owner;
""",
    r"""
GRANT EXECUTE ON FUNCTION aria_internal.fail_preview(UUID, UUID, TEXT) TO aria_worker;
""",
)


def upgrade() -> None:
    for statement in _STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    # No table/role/data removal. Existing 0040 guards remain unchanged downstream.
    op.execute("DROP FUNCTION aria_internal.fail_preview(UUID, UUID, TEXT)")
    op.execute("REVOKE SELECT (error_code) ON public.jobs FROM aria_preview_runtime_owner")
