"""Apply the reviewed Local/Synthetic Preview authority contract; no Hosted activation."""

from alembic import op
from sqlalchemy import text

revision: str = "0040_preview_publication"
down_revision: str | None = "0039_artifact_generation_runtime"
branch_labels: str | None = None
depends_on: str | None = None

# Literal statements mechanically copied from the owner-reviewed SQL source.
# No runtime dependency on docs and no generic SQL/table-selection API.
_STATEMENTS: tuple[str, ...] = (
    r"""
-- Activated only for owner-authorized throwaway Local/Synthetic verification.
-- Executable statements match the immutable SQL review source; no Hosted authorization.
-- Target table owner stays the migration principal. Helper owner owns functions ONLY.
-- Four runtime helpers; two SECURITY INVOKER trigger functions provide DB invariants.

CREATE TABLE public.preview_representations (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE RESTRICT,
    project_id UUID NOT NULL,
    artifact_id UUID NOT NULL,
    artifact_version_id UUID NOT NULL,
    source_hash VARCHAR(71) NOT NULL CHECK (source_hash ~ '^sha256:[0-9a-f]{64}$'),
    transformer_version TEXT NOT NULL CHECK (transformer_version =
    'preview_delivery_transformer_v1'),
    delivery_policy_version TEXT NOT NULL CHECK (delivery_policy_version =
    'preview_delivery_policy_v1'),
    status TEXT NOT NULL CHECK (status IN ('allocated', 'preparing', 'ready')),
    manifest_ref TEXT,
    manifest_hash VARCHAR(71),
    created_by UUID NOT NULL REFERENCES public.profiles(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_preview_representation_source
        FOREIGN KEY (artifact_version_id, artifact_id, account_id, project_id)
        REFERENCES public.artifact_versions(id, artifact_id, account_id, project_id) ON DELETE
        RESTRICT,
    CONSTRAINT uq_preview_representation_profile
        UNIQUE (account_id, artifact_version_id, transformer_version, delivery_policy_version),
    CONSTRAINT uq_preview_representation_tenant_version
        UNIQUE (id, artifact_version_id, account_id, project_id),
    CONSTRAINT preview_representation_manifest CHECK (
        (status = 'ready' AND manifest_ref IS NOT NULL AND LENGTH(BTRIM(manifest_ref)) > 0
         AND manifest_hash IS NOT NULL AND manifest_hash ~ '^sha256:[0-9a-f]{64}$')
        OR (status <> 'ready' AND manifest_ref IS NULL AND manifest_hash IS NULL)
    )
);
""",
    r"""
CREATE INDEX ix_preview_representation_tenant
    ON public.preview_representations(account_id, project_id);
""",
    r"""
CREATE TABLE public.preview_publications (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES public.accounts(id) ON DELETE RESTRICT,
    project_id UUID NOT NULL,
    artifact_version_id UUID NOT NULL,
    representation_id UUID NOT NULL,
    publish_job_id UUID NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('allocated', 'publishing', 'ready', 'revoked')),
    created_by UUID NOT NULL REFERENCES public.profiles(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    token_hash VARCHAR(64),
    expires_at TIMESTAMPTZ,
    issued_at TIMESTAMPTZ,
    CONSTRAINT fk_preview_publication_representation
        FOREIGN KEY (representation_id, artifact_version_id, account_id, project_id)
        REFERENCES public.preview_representations(id, artifact_version_id, account_id,
        project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_preview_publication_job
        FOREIGN KEY (publish_job_id, account_id, project_id)
        REFERENCES public.jobs(id, account_id, project_id) ON DELETE RESTRICT,
    CONSTRAINT uq_preview_publication_job UNIQUE (publish_job_id),
    CONSTRAINT uq_preview_publication_tenant UNIQUE (id, account_id, project_id),
    CONSTRAINT uq_preview_publication_capability UNIQUE (token_hash),
    CONSTRAINT preview_revocation CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
    CONSTRAINT preview_capability_complete CHECK (
        (token_hash IS NULL AND expires_at IS NULL AND issued_at IS NULL)
        OR (token_hash IS NOT NULL AND token_hash ~ '^[0-9a-f]{64}$'
            AND expires_at IS NOT NULL AND issued_at IS NOT NULL
            AND expires_at > issued_at AND status IN ('ready', 'revoked'))
    )
);
""",
    r"""
CREATE INDEX ix_preview_publication_tenant ON public.preview_publications(account_id,
project_id);
""",
    r"""
CREATE UNIQUE INDEX uq_jobs_active_preview_representation
    ON public.jobs(account_id, project_id, (payload_ref ->> 'representation_id'))
    WHERE job_type = 'preview_publication' AND status IN ('queued', 'running');
""",
    r"""
-- Operational execution ownership, not a third content/capability aggregate.
CREATE TABLE aria_internal.preview_execution_claims (
    job_id UUID PRIMARY KEY REFERENCES public.jobs(id) ON DELETE RESTRICT,
    outbox_event_id UUID NOT NULL REFERENCES public.outbox_events(id) ON DELETE RESTRICT,
    owner_backend_pid INTEGER NOT NULL
);
""",
    r"""
CREATE ROLE aria_preview_runtime_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
""",
    r"""
GRANT USAGE ON SCHEMA public, aria_internal TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT ON public.preview_representations, public.preview_publications
    TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT (id, account_id, project_id, artifact_id, status, artifact_hash, version_no,
storage_ref)
    ON public.artifact_versions TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT (id, account_id, project_id) ON public.artifacts TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT (id, account_id) ON public.projects TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT (id) ON public.accounts TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT (id, account_id, project_id, job_type, status, payload_ref, started_at,
attempt_count)
    ON public.jobs TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT (id, account_id, aggregate_id, aggregate_type, event_type, delivery_channel,
payload)
    ON public.outbox_events TO aria_preview_runtime_owner;
""",
    r"""
GRANT UPDATE (status, manifest_ref, manifest_hash)
    ON public.preview_representations TO aria_preview_runtime_owner;
""",
    r"""
GRANT UPDATE (status) ON public.preview_publications TO aria_preview_runtime_owner;
""",
    r"""
GRANT UPDATE (status, started_at, finished_at, error_code, error_detail, attempt_count)
    ON public.jobs TO aria_preview_runtime_owner;
""",
    r"""
GRANT SELECT, INSERT, UPDATE, DELETE ON aria_internal.preview_execution_claims
    TO aria_preview_runtime_owner;
""",
    r"""
ALTER TABLE public.preview_representations ENABLE ROW LEVEL SECURITY;
""",
    r"""
ALTER TABLE public.preview_publications ENABLE ROW LEVEL SECURITY;
""",
    r"""
ALTER TABLE aria_internal.preview_execution_claims ENABLE ROW LEVEL SECURITY;
""",
    r"""
CREATE POLICY preview_representations_owner_select ON public.preview_representations
    FOR SELECT TO aria_preview_runtime_owner USING (true);
""",
    r"""
CREATE POLICY preview_representations_owner_update ON public.preview_representations
    FOR UPDATE TO aria_preview_runtime_owner USING (true) WITH CHECK (true);
""",
    r"""
CREATE POLICY preview_publications_owner_select ON public.preview_publications
    FOR SELECT TO aria_preview_runtime_owner USING (true);
""",
    r"""
CREATE POLICY preview_publications_owner_update ON public.preview_publications
    FOR UPDATE TO aria_preview_runtime_owner USING (true) WITH CHECK (true);
""",
    r"""
CREATE POLICY preview_execution_claims_owner ON aria_internal.preview_execution_claims
    TO aria_preview_runtime_owner USING (true) WITH CHECK (true);
""",
    r"""
CREATE POLICY artifact_versions_preview_owner_select ON public.artifact_versions
    FOR SELECT TO aria_preview_runtime_owner USING (true);
""",
    r"""
CREATE POLICY artifacts_preview_owner_select ON public.artifacts
    FOR SELECT TO aria_preview_runtime_owner USING (true);
""",
    r"""
CREATE POLICY projects_preview_owner_select ON public.projects
    FOR SELECT TO aria_preview_runtime_owner USING (true);
""",
    r"""
CREATE POLICY accounts_preview_owner_select ON public.accounts
    FOR SELECT TO aria_preview_runtime_owner USING (true);
""",
    r"""
CREATE POLICY jobs_preview_owner_select ON public.jobs
    FOR SELECT TO aria_preview_runtime_owner USING (job_type = 'preview_publication');
""",
    r"""
CREATE POLICY jobs_preview_owner_update ON public.jobs
    FOR UPDATE TO aria_preview_runtime_owner
    USING (job_type = 'preview_publication') WITH CHECK (job_type = 'preview_publication');
""",
    r"""
CREATE POLICY outbox_preview_owner_select ON public.outbox_events
    FOR SELECT TO aria_preview_runtime_owner
    USING (event_type = 'preview.publication_requested.v1' AND delivery_channel = 'job_queue');
""",
    r"""
REVOKE ALL ON public.preview_representations, public.preview_publications,
    aria_internal.preview_execution_claims FROM PUBLIC, aria_worker;
""",
    r"""
-- No new grant to anon/authenticated. Fresh tables have no such direct privileges.

-- SECURITY INVOKER invariant triggers; no runtime grant or generic SQL capability.
CREATE FUNCTION public.protect_preview_representation() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $body$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Preview deletion denied' USING ERRCODE = '55000';
    END IF;
    IF (NEW.id, NEW.account_id, NEW.project_id, NEW.artifact_id, NEW.artifact_version_id,
        NEW.source_hash, NEW.transformer_version, NEW.delivery_policy_version,
        NEW.created_by, NEW.created_at)
       IS DISTINCT FROM (OLD.id, OLD.account_id, OLD.project_id, OLD.artifact_id,
        OLD.artifact_version_id, OLD.source_hash, OLD.transformer_version,
        OLD.delivery_policy_version, OLD.created_by, OLD.created_at)
       OR (OLD.status = 'ready' AND NEW IS DISTINCT FROM OLD)
       OR NOT (NEW.status = OLD.status
            OR (OLD.status = 'allocated' AND NEW.status = 'preparing')
            OR (OLD.status = 'preparing' AND NEW.status = 'ready')) THEN
        RAISE EXCEPTION 'Preview representation transition denied' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$body$;
""",
    r"""
REVOKE ALL ON FUNCTION public.protect_preview_representation() FROM PUBLIC;
""",
    r"""
CREATE TRIGGER trg_preview_representation_protect BEFORE UPDATE OR DELETE
    ON public.preview_representations FOR EACH ROW
    EXECUTE FUNCTION public.protect_preview_representation();
""",
    r"""
CREATE FUNCTION public.protect_preview_publication() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $body$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Preview deletion denied' USING ERRCODE = '55000';
    END IF;
    IF (NEW.id, NEW.account_id, NEW.project_id, NEW.artifact_version_id,
        NEW.representation_id, NEW.publish_job_id, NEW.created_by, NEW.created_at)
       IS DISTINCT FROM (OLD.id, OLD.account_id, OLD.project_id, OLD.artifact_version_id,
        OLD.representation_id, OLD.publish_job_id, OLD.created_by, OLD.created_at)
       OR (OLD.status = 'revoked' AND NEW IS DISTINCT FROM OLD)
       OR (OLD.token_hash IS NOT NULL AND (NEW.token_hash, NEW.expires_at, NEW.issued_at)
           IS DISTINCT FROM (OLD.token_hash, OLD.expires_at, OLD.issued_at))
       OR NOT (NEW.status = OLD.status OR NEW.status = 'revoked'
            OR (OLD.status = 'allocated' AND NEW.status = 'publishing')
            OR (OLD.status = 'publishing' AND NEW.status = 'ready')) THEN
        RAISE EXCEPTION 'Preview publication transition denied' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$body$;
""",
    r"""
REVOKE ALL ON FUNCTION public.protect_preview_publication() FROM PUBLIC;
""",
    r"""
CREATE TRIGGER trg_preview_publication_protect BEFORE UPDATE OR DELETE
    ON public.preview_publications FOR EACH ROW
    EXECUTE FUNCTION public.protect_preview_publication();
""",
    r"""
CREATE FUNCTION aria_internal.claim_preview(p_job UUID, p_event UUID) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $body$
DECLARE b RECORD; k BIGINT;
BEGIN
    IF p_job IS NULL OR p_event IS NULL THEN
        RAISE EXCEPTION 'Preview identity denied' USING ERRCODE = '42501';
    END IF;
    -- Fixed lock order: Job -> Publication -> Representation. No external work in transaction.
    PERFORM j.id FROM public.jobs AS j WHERE j.id = p_job AND j.job_type = 'preview_publication'
        FOR UPDATE;
    PERFORM p.id FROM public.preview_publications AS p WHERE p.publish_job_id = p_job FOR
    UPDATE;
    PERFORM r.id FROM public.preview_representations AS r
        JOIN public.preview_publications AS p ON p.representation_id = r.id
        WHERE p.publish_job_id = p_job FOR UPDATE OF r;

    -- Revalidate every association AFTER the mutation targets are locked.
    -- Ready source metadata/identity are immutable; no UPDATE grant to lock source tables is added.
    SELECT j.id AS job_id, j.status AS job_status, p.id AS publication_id, p.status AS
    publication_status,
        r.id AS representation_id, r.account_id, r.project_id, r.artifact_id,
        r.artifact_version_id,
        r.source_hash, r.manifest_ref, r.manifest_hash, a.version_no, a.storage_ref AS
        source_ref
    INTO b
    FROM public.jobs AS j
    JOIN public.preview_publications AS p ON p.publish_job_id = j.id
        AND (p.account_id, p.project_id) = (j.account_id, j.project_id)
    JOIN public.preview_representations AS r ON
        (r.id, r.account_id, r.project_id, r.artifact_version_id) =
        (p.representation_id, p.account_id, p.project_id, p.artifact_version_id)
    JOIN public.artifact_versions AS a ON
        (a.id, a.artifact_id, a.account_id, a.project_id) =
        (r.artifact_version_id, r.artifact_id, r.account_id, r.project_id)
    JOIN public.artifacts AS ar ON (ar.id, ar.account_id, ar.project_id) =
        (a.artifact_id, a.account_id, a.project_id)
    JOIN public.projects AS pr ON (pr.id, pr.account_id) = (ar.project_id, ar.account_id)
    JOIN public.accounts AS ac ON ac.id = pr.account_id
    JOIN public.outbox_events AS e ON e.id = p_event AND e.account_id = j.account_id
        AND e.aggregate_type = 'job' AND e.aggregate_id = j.id
        AND e.event_type = 'preview.publication_requested.v1' AND e.delivery_channel =
        'job_queue'
        AND e.payload = pg_catalog.jsonb_build_object('jobId', j.id::TEXT,
            'taskType', 'preview_publication', 'payloadVersion', '1')
    WHERE j.id = p_job AND j.job_type = 'preview_publication'
        AND j.status IN ('queued', 'running', 'succeeded')
        AND j.payload_ref = pg_catalog.jsonb_build_object('publication_id', p.id::TEXT,
            'representation_id', r.id::TEXT, 'artifact_version_id', a.id::TEXT)
        AND a.status = 'ready' AND a.artifact_hash = r.source_hash
        AND r.transformer_version = 'preview_delivery_transformer_v1'
        AND r.delivery_policy_version = 'preview_delivery_policy_v1'
        AND p.revoked_at IS NULL AND p.status IN ('allocated', 'publishing', 'ready');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Preview binding denied' USING ERRCODE = '42501';
    END IF;
    IF b.job_status = 'succeeded' THEN
        IF b.publication_status <> 'ready' OR b.manifest_hash IS NULL OR b.manifest_ref IS NULL
        THEN
            RAISE EXCEPTION 'Preview success binding denied' USING ERRCODE = '42501';
        END IF;
    ELSE
        IF b.publication_status = 'ready' THEN
            RAISE EXCEPTION 'Preview execution state denied' USING ERRCODE = '42501';
        END IF;
        k := pg_catalog.hashtextextended('aria:preview:' || p_job::TEXT, 0);
        IF NOT pg_catalog.pg_try_advisory_lock(k) THEN
            RAISE EXCEPTION 'Preview execution in progress' USING ERRCODE = '55P03';
        END IF;
        -- Do not reacquire reentrant ownership on the same backend and leak a lock count.
        IF EXISTS (SELECT 1 FROM aria_internal.preview_execution_claims AS c
            WHERE c.job_id = p_job AND c.owner_backend_pid = pg_catalog.pg_backend_pid()) THEN
            PERFORM pg_catalog.pg_advisory_unlock(k);
            RAISE EXCEPTION 'Preview execution already owned' USING ERRCODE = '55P03';
        END IF;
        INSERT INTO aria_internal.preview_execution_claims(job_id, outbox_event_id,
        owner_backend_pid)
            VALUES (p_job, p_event, pg_catalog.pg_backend_pid())
            ON CONFLICT (job_id) DO UPDATE SET outbox_event_id = EXCLUDED.outbox_event_id,
                owner_backend_pid = EXCLUDED.owner_backend_pid;
        UPDATE public.jobs SET status = 'running',
            started_at = COALESCE(started_at, CURRENT_TIMESTAMP), attempt_count =
            GREATEST(attempt_count, 1)
            WHERE id = p_job;
        UPDATE public.preview_publications SET status = 'publishing' WHERE id =
        b.publication_id;
        UPDATE public.preview_representations SET status = 'preparing'
            WHERE id = b.representation_id AND status = 'allocated';
    END IF;
    RETURN pg_catalog.jsonb_build_object('job_id', p_job, 'publication_id', b.publication_id,
        'account_id', b.account_id, 'project_id', b.project_id, 'artifact_id', b.artifact_id,
        'artifact_version_id', b.artifact_version_id, 'version_no', b.version_no,
        'representation_id', b.representation_id, 'source_hash', b.source_hash,
        'source_ref', b.source_ref, 'manifest_ref', b.manifest_ref, 'manifest_hash',
        b.manifest_hash,
        'already_completed', b.job_status = 'succeeded');
END;
$body$;
""",
    r"""
CREATE FUNCTION aria_internal.finalize_preview(
    p_job UUID, p_event UUID, p_ref TEXT, p_hash TEXT
) RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $body$
DECLARE b RECORD;
BEGIN
    IF p_job IS NULL OR p_event IS NULL OR p_ref IS NULL OR p_hash IS NULL THEN
        RAISE EXCEPTION 'Preview identity denied' USING ERRCODE = '42501';
    END IF;
    PERFORM j.id FROM public.jobs AS j WHERE j.id = p_job AND j.job_type = 'preview_publication'
        FOR UPDATE;
    PERFORM p.id FROM public.preview_publications AS p WHERE p.publish_job_id = p_job FOR
    UPDATE;
    PERFORM r.id FROM public.preview_representations AS r
        JOIN public.preview_publications AS p ON p.representation_id = r.id
        WHERE p.publish_job_id = p_job FOR UPDATE OF r;
    SELECT p.id AS publication_id, p.status AS publication_status,
        r.id AS representation_id, r.status AS representation_status,
        r.account_id, r.project_id, r.artifact_version_id, r.manifest_ref, r.manifest_hash
    INTO b
    FROM aria_internal.preview_execution_claims AS c
    JOIN public.jobs AS j ON j.id = c.job_id AND j.job_type = 'preview_publication' AND
    j.status = 'running'
    JOIN public.preview_publications AS p ON p.publish_job_id = j.id
        AND (p.account_id, p.project_id) = (j.account_id, j.project_id)
    JOIN public.preview_representations AS r ON
        (r.id, r.artifact_version_id, r.account_id, r.project_id) =
        (p.representation_id, p.artifact_version_id, p.account_id, p.project_id)
    JOIN public.artifact_versions AS a ON
        (a.id, a.artifact_id, a.account_id, a.project_id) =
        (r.artifact_version_id, r.artifact_id, r.account_id, r.project_id)
    JOIN public.artifacts AS ar ON (ar.id, ar.account_id, ar.project_id) = (a.artifact_id,
    a.account_id, a.project_id)
    JOIN public.projects AS pr ON (pr.id, pr.account_id) = (ar.project_id, ar.account_id)
    JOIN public.accounts AS ac ON ac.id = pr.account_id
    JOIN public.outbox_events AS e ON e.id = c.outbox_event_id AND e.id = p_event
        AND e.account_id = j.account_id AND e.aggregate_type = 'job' AND e.aggregate_id = j.id
        AND e.event_type = 'preview.publication_requested.v1' AND e.delivery_channel =
        'job_queue'
        AND e.payload = pg_catalog.jsonb_build_object('jobId', j.id::TEXT,
            'taskType', 'preview_publication', 'payloadVersion', '1')
    WHERE c.job_id = p_job AND c.owner_backend_pid = pg_catalog.pg_backend_pid()
        AND a.status = 'ready' AND a.artifact_hash = r.source_hash
        AND j.payload_ref = pg_catalog.jsonb_build_object('publication_id', p.id::TEXT,
            'representation_id', r.id::TEXT, 'artifact_version_id', a.id::TEXT)
        AND p.status = 'publishing' AND p.revoked_at IS NULL
        AND r.transformer_version = 'preview_delivery_transformer_v1'
        AND r.delivery_policy_version = 'preview_delivery_policy_v1';
    IF NOT FOUND OR p_ref IS NULL OR p_hash IS NULL
        OR p_hash !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Preview finalization denied' USING ERRCODE = '42501';
    END IF;
    IF p_ref <> 'preview/' || b.account_id::TEXT || '/' || b.project_id::TEXT || '/' ||
        b.artifact_version_id::TEXT || '/' || b.representation_id::TEXT ||
        '/delivery-manifest.json' THEN
        RAISE EXCEPTION 'Preview namespace denied' USING ERRCODE = '42501';
    END IF;
    IF b.representation_status = 'ready' THEN
        IF (b.manifest_ref, b.manifest_hash) IS DISTINCT FROM (p_ref, p_hash) THEN
            RAISE EXCEPTION 'Preview immutable conflict' USING ERRCODE = '23514';
        END IF;
    ELSIF b.representation_status = 'preparing' THEN
        UPDATE public.preview_representations SET status = 'ready', manifest_ref = p_ref,
            manifest_hash = p_hash WHERE id = b.representation_id;
    ELSE
        RAISE EXCEPTION 'Preview preparation denied' USING ERRCODE = '42501';
    END IF;
    UPDATE public.preview_publications SET status = 'ready' WHERE id = b.publication_id;
    UPDATE public.jobs SET status = 'succeeded', finished_at = CURRENT_TIMESTAMP,
        error_code = NULL, error_detail = NULL WHERE id = p_job;
END;
$body$;
""",
    r"""
CREATE FUNCTION aria_internal.release_preview(p_job UUID, p_event UUID) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $body$
BEGIN
    IF p_job IS NULL OR p_event IS NULL THEN
        RAISE EXCEPTION 'Preview identity denied' USING ERRCODE = '42501';
    END IF;
    DELETE FROM aria_internal.preview_execution_claims AS c
        WHERE c.job_id = p_job AND c.outbox_event_id = p_event
            AND c.owner_backend_pid = pg_catalog.pg_backend_pid();
    IF FOUND THEN
        PERFORM pg_catalog.pg_advisory_unlock(
            pg_catalog.hashtextextended('aria:preview:' || p_job::TEXT, 0));
    END IF;
END;
$body$;
""",
    r"""
CREATE FUNCTION aria_internal.resolve_preview(p_hash TEXT) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $body$
DECLARE result JSONB;
BEGIN
    IF p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$' THEN
        RETURN NULL;
    END IF;
    -- Take the revocation-ordering lock before checking expiry/association. Use wall time
    -- after lock acquisition, not the transaction-start timestamp from before a possible wait.
    PERFORM p.id FROM public.preview_publications AS p WHERE p.token_hash = p_hash FOR SHARE;
    SELECT pg_catalog.jsonb_build_object('account_id', r.account_id, 'project_id', r.project_id,
        'artifact_id', r.artifact_id, 'artifact_version_id', a.id, 'version_no', a.version_no,
        'representation_id', r.id, 'source_hash', r.source_hash, 'source_ref', a.storage_ref,
        'manifest_ref', r.manifest_ref, 'manifest_hash', r.manifest_hash)
    INTO result
    FROM public.preview_publications AS p
    JOIN public.preview_representations AS r ON
        (r.id, r.artifact_version_id, r.account_id, r.project_id) =
        (p.representation_id, p.artifact_version_id, p.account_id, p.project_id)
    JOIN public.artifact_versions AS a ON
        (a.id, a.artifact_id, a.account_id, a.project_id) =
        (r.artifact_version_id, r.artifact_id, r.account_id, r.project_id)
    JOIN public.artifacts AS ar ON (ar.id, ar.account_id, ar.project_id) = (a.artifact_id,
    a.account_id, a.project_id)
    JOIN public.projects AS pr ON (pr.id, pr.account_id) = (ar.project_id, ar.account_id)
    JOIN public.accounts AS ac ON ac.id = pr.account_id
    WHERE p_hash ~ '^[0-9a-f]{64}$' AND p.token_hash = p_hash
        AND p.status = 'ready' AND p.revoked_at IS NULL
        AND p.expires_at > pg_catalog.clock_timestamp()
        AND r.status = 'ready' AND a.status = 'ready' AND a.artifact_hash = r.source_hash
        AND r.transformer_version = 'preview_delivery_transformer_v1'
        AND r.delivery_policy_version = 'preview_delivery_policy_v1';
    RETURN result;
END;
$body$;
""",
    r"""
REVOKE ALL ON FUNCTION aria_internal.claim_preview(UUID, UUID) FROM PUBLIC;
""",
    r"""
REVOKE ALL ON FUNCTION aria_internal.finalize_preview(UUID, UUID, TEXT, TEXT) FROM PUBLIC;
""",
    r"""
REVOKE ALL ON FUNCTION aria_internal.release_preview(UUID, UUID) FROM PUBLIC;
""",
    r"""
REVOKE ALL ON FUNCTION aria_internal.resolve_preview(TEXT) FROM PUBLIC;
""",
    r"""
ALTER FUNCTION aria_internal.claim_preview(UUID, UUID) OWNER TO aria_preview_runtime_owner;
""",
    r"""
ALTER FUNCTION aria_internal.finalize_preview(UUID, UUID, TEXT, TEXT) OWNER TO
aria_preview_runtime_owner;
""",
    r"""
ALTER FUNCTION aria_internal.release_preview(UUID, UUID) OWNER TO aria_preview_runtime_owner;
""",
    r"""
ALTER FUNCTION aria_internal.resolve_preview(TEXT) OWNER TO aria_preview_runtime_owner;
""",
    r"""
GRANT EXECUTE ON FUNCTION aria_internal.claim_preview(UUID, UUID) TO aria_worker;
""",
    r"""
GRANT EXECUTE ON FUNCTION aria_internal.finalize_preview(UUID, UUID, TEXT, TEXT) TO aria_worker;
""",
    r"""
GRANT EXECUTE ON FUNCTION aria_internal.release_preview(UUID, UUID) TO aria_worker;
""",
    r"""
GRANT EXECUTE ON FUNCTION aria_internal.resolve_preview(TEXT) TO aria_worker;
""",
    r"""
-- Explicitly remove optional Data API role privileges, including inherited default grants.
-- Fixed role names and fixed objects only; no dynamic SQL or generic relation targeting.
DO $roles$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.preview_representations, public.preview_publications,
            aria_internal.preview_execution_claims FROM anon;
        REVOKE ALL ON FUNCTION aria_internal.claim_preview(UUID, UUID),
            aria_internal.finalize_preview(UUID, UUID, TEXT, TEXT),
            aria_internal.release_preview(UUID, UUID), aria_internal.resolve_preview(TEXT) FROM
            anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.preview_representations, public.preview_publications,
            aria_internal.preview_execution_claims FROM authenticated;
        REVOKE ALL ON FUNCTION aria_internal.claim_preview(UUID, UUID),
            aria_internal.finalize_preview(UUID, UUID, TEXT, TEXT),
            aria_internal.release_preview(UUID, UUID),
            aria_internal.resolve_preview(TEXT) FROM authenticated;
    END IF;
END;
$roles$;
""",
)


def upgrade() -> None:
    for statement in _STATEMENTS:
        if statement.lstrip().startswith("CREATE ROLE aria_preview_runtime_owner"):
            attributes = (
                op.get_bind()
                .execute(
                    text(
                        "SELECT rolcanlogin, rolinherit, rolsuper, rolbypassrls, rolcreatedb, "
                        "rolcreaterole, rolreplication FROM pg_catalog.pg_roles "
                        "WHERE rolname='aria_preview_runtime_owner'"
                    )
                )
                .first()
            )
            if attributes is not None:
                if any(attributes):
                    raise RuntimeError("Preview runtime owner attributes rejected")
                # Cluster Role may survive another database's guarded downgrade.
                # Reuse does not ALTER attributes, grant memberships or broaden runtime access.
                continue
        op.execute(statement)


def downgrade() -> None:
    # Hold exclusive locks through the same DDL transaction: no check-then-drop write race.
    op.execute(
        "LOCK TABLE public.preview_publications, public.preview_representations, "
        "aria_internal.preview_execution_claims IN ACCESS EXCLUSIVE MODE"
    )
    populated = op.get_bind().scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM public.preview_publications) "
            "OR EXISTS (SELECT 1 FROM public.preview_representations) "
            "OR EXISTS (SELECT 1 FROM aria_internal.preview_execution_claims)"
        )
    )
    if populated:
        raise RuntimeError("Preview downgrade denied: state exists")

    for signature in (
        "claim_preview(uuid, uuid)",
        "finalize_preview(uuid, uuid, text, text)",
        "release_preview(uuid, uuid)",
        "resolve_preview(text)",
    ):
        op.execute(f"DROP FUNCTION aria_internal.{signature}")
    op.execute("DROP TABLE aria_internal.preview_execution_claims")
    op.execute("DROP TABLE public.preview_publications")
    op.execute("DROP TABLE public.preview_representations")
    op.execute("DROP FUNCTION public.protect_preview_publication()")
    op.execute("DROP FUNCTION public.protect_preview_representation()")
    op.execute("DROP INDEX public.uq_jobs_active_preview_representation")
    op.execute("DROP POLICY jobs_preview_owner_update ON public.jobs")

    # Revoke the exact column ACLs, not merely table-level privileges. Preserve all other Roles.
    read_columns = {
        "artifact_versions": "id, account_id, project_id, artifact_id, status, artifact_hash, "
        "version_no, storage_ref",
        "artifacts": "id, account_id, project_id",
        "projects": "id, account_id",
        "accounts": "id",
        "jobs": "id, account_id, project_id, job_type, status, payload_ref, "
        "started_at, attempt_count",
        "outbox_events": "id, account_id, aggregate_id, aggregate_type, event_type, "
        "delivery_channel, payload",
    }
    for relation, columns in read_columns.items():
        policy = (
            "outbox_preview_owner_select"
            if relation == "outbox_events"
            else (f"{relation}_preview_owner_select")
        )
        op.execute(f"DROP POLICY {policy} ON public.{relation}")
        op.execute(
            f"REVOKE SELECT ({columns}) ON public.{relation} FROM aria_preview_runtime_owner"
        )
    op.execute(
        "REVOKE UPDATE (status, started_at, finished_at, error_code, error_detail, attempt_count) "
        "ON public.jobs FROM aria_preview_runtime_owner"
    )
    op.execute("REVOKE USAGE ON SCHEMA public, aria_internal FROM aria_preview_runtime_owner")
    outside_dependency = op.get_bind().scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_shdepend d "
            "JOIN pg_catalog.pg_roles r ON r.oid=d.refobjid "
            "WHERE r.rolname='aria_preview_runtime_owner' "
            "AND d.refclassid='pg_catalog.pg_authid'::pg_catalog.regclass "
            "AND d.dbid <> (SELECT oid FROM pg_catalog.pg_database "
            "WHERE datname=pg_catalog.current_database()))"
        )
    )
    if not outside_dependency:
        # PostgreSQL's dependency check remains the final race guard: unexpected dependencies
        # abort the entire transaction. Never use DROP OWNED or CASCADE to force removal.
        op.execute("DROP ROLE aria_preview_runtime_owner")
