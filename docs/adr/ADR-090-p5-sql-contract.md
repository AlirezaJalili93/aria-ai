# ADR-090 P5 — Proposed Bootstrap Consumption SQL Contract

**Status: PENDING OWNER SOURCE REVIEW / NOT COMPILED / NOT EXECUTED.**

Date: 2026-10-17. Parent: [ADR-090](ADR-090-controlled-preview-workspace-contract.md).
Scope: Local/Synthetic SQL design only. This Markdown is not a migration, application module,
fixture loader or permission to run any statement. P5 logical model and Option A design are
approved; exact DDL, function signatures, grants and role-owner reuse below are proposals.
P4/full ADR Freeze WAIT; Runtime, Migration, Hosted/customer use and commit/push NO-GO.

## 1. Authority, dependencies and exclusions

Authority: owner's explicit P5 review and subsequent answer selecting **valid Capability plus
stored database binding** as the authentication boundary. Public P1 still has only `token` in its
body, no new JWT/Tenant header or Core assertion. Application applies approved P2/P3 Host/Origin,
body-size/encoding/shape guards before calling SQL. The server hashes the canonical token; neither
helper accepts raw token or a caller-selected tenant as authority. Tenant/project are resolved
from the unique stored hash and checked through the complete binding graph. Core management JWT/
membership authorization is unchanged. Origin alone is not authorization.

Repository sources, read 2026-10-17:

- [0040](../../apps/api/migrations/versions/0040_preview_publication.py): immutable Publication/
  Representation identities, composite keys, fixed v1 resolver and restricted helper owner.
- [0041](../../apps/api/migrations/versions/0041_preview_failure.py): existing fixed failure helper.
- [0038](../../apps/api/migrations/versions/0038_artifact_version_foundation.py): ready ArtifactVersion
  rows and source identity are immutable.
- [Revoke repository](../../apps/api/app/modules/generation/infrastructure/preview_repository.py):
  existing Job -> Publication lock order. No code changes proposed in this file.
- [Governance](../governance/document-driven-development.md), [ADR-089](ADR-089-local-preview-publication-and-capability.md)
  and parent's existing Canonical links/sync dates. No fresh Drive review claimed.

Technical review: PostgreSQL 16 [SELECT privileges/locks](https://www.postgresql.org/docs/16/sql-select.html),
[RLS](https://www.postgresql.org/docs/16/ddl-rowsecurity.html) and
[SECURITY DEFINER](https://www.postgresql.org/docs/16/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).
The PostgreSQL skill guided short transactions, explicit lock order and minimum new ACLs, not
timeouts, role redesign or product defaults. New-table RLS is not a redesign of existing Worker SELECT.

**Dependency:** the two P1 version strings below are the unapproved P4 candidates. Current 0040
CHECKs still allow only v1. This document deliberately does not alter those CHECKs or old claim/
finalize/fail/resolve functions. Approval/application of this consumption design alone cannot make
P1 publishable. P4 identities, packet Manifest schema and additive publishing SQL need their own
source review first; changing either version string requires revising this source, not runtime input.

## 2. Proposed objects and new authority

| Object / principal | Proposed boundary |
|---|---|
| `aria_internal.preview_bootstrap_consumptions` | Four approved logical fields; append-only; PK is Publication identity |
| Existing `aria_preview_runtime_owner` | Proposed function owner; reuse reviewed NOLOGIN/NOBYPASSRLS owner, not table ownership; ledger SELECT(publication_id) and INSERT of the four fields only |
| Existing `aria_worker` | EXECUTE only on two exact helpers; no ledger SELECT/INSERT/UPDATE/DELETE/TRUNCATE |
| PUBLIC / anon / authenticated | No ledger access or new helper execution |
| Migration principal | Future separately authorized DDL only; must not be helper owner; cannot be used as runtime evidence |

Owner reuse is proposed explicitly, not silently granted. Its existing Job/Publication rights serve
the reviewed 0102 helper family; this design adds no parent-table, Job or role-membership privileges.
It does not claim a per-function dedicated role or isolation after shared-Worker compromise.
The ledger is not owned by the helper owner and has FORCE RLS. Its definer-owner policies check
the stored tenant/project/profile association; callers cannot set a tenant GUC to authorize a row.
The owner can access eligible P1 rows across tenants inside trusted fixed functions; RLS does not
independently authenticate a request's Capability. The helper hash predicates do that. This is a
limited Local/Synthetic boundary, not a Production shared-credential security assessment.

## 3. Proposed DDL and ledger protection — review text only

Future approved installation must be one DDL transaction so default PUBLIC function execution is
revoked before commit. Do not use IF NOT EXISTS/OR REPLACE to trust or overwrite unknown objects.
No DDL transaction or database connection has been opened for this draft.

```sql
-- NOT EXECUTED. Only after explicit source approval and a separate execution authorization.
DO $guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'aria_preview_runtime_owner'
          AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
          AND NOT rolinherit
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'aria_worker' AND NOT rolsuper AND NOT rolbypassrls
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
    ) THEN
        RAISE EXCEPTION 'Preview role prerequisites denied' USING ERRCODE = '42501';
    END IF;
    IF CURRENT_USER = 'aria_preview_runtime_owner'
       OR pg_catalog.pg_has_role('aria_worker', 'aria_preview_runtime_owner', 'MEMBER')
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members AS m
           JOIN pg_catalog.pg_roles AS r ON r.oid = m.member
           WHERE r.rolname = 'aria_preview_runtime_owner'
       )
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_class AS c
           JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
           JOIN pg_catalog.pg_roles AS r ON r.oid = c.relowner
           WHERE n.nspname = 'public'
             AND c.relname IN ('preview_publications', 'preview_representations',
                              'artifact_versions', 'artifacts', 'projects', 'accounts')
             AND r.rolname = 'aria_preview_runtime_owner'
       ) THEN
        RAISE EXCEPTION 'Preview owner boundary denied' USING ERRCODE = '42501';
    END IF;
END;
$guard$;

CREATE TABLE aria_internal.preview_bootstrap_consumptions (
    publication_id UUID PRIMARY KEY,
    account_id UUID NOT NULL,
    project_id UUID NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_bootstrap_consumption_publication
        FOREIGN KEY (publication_id, account_id, project_id)
        REFERENCES public.preview_publications(id, account_id, project_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

ALTER TABLE aria_internal.preview_bootstrap_consumptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE aria_internal.preview_bootstrap_consumptions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE aria_internal.preview_bootstrap_consumptions
    FROM PUBLIC, aria_worker, aria_preview_runtime_owner;
GRANT SELECT (publication_id),
      INSERT (publication_id, account_id, project_id, consumed_at)
    ON TABLE aria_internal.preview_bootstrap_consumptions TO aria_preview_runtime_owner;

CREATE POLICY bootstrap_consumption_owner_select
ON aria_internal.preview_bootstrap_consumptions
FOR SELECT TO aria_preview_runtime_owner
USING (EXISTS (
    SELECT 1 FROM public.preview_publications AS p
    JOIN public.preview_representations AS r ON
        (r.id, r.artifact_version_id, r.account_id, r.project_id) =
        (p.representation_id, p.artifact_version_id, p.account_id, p.project_id)
    WHERE (p.id, p.account_id, p.project_id) =
          (preview_bootstrap_consumptions.publication_id,
           preview_bootstrap_consumptions.account_id,
           preview_bootstrap_consumptions.project_id)
      AND r.transformer_version = 'preview_bootstrap_transformer_v1'
      AND r.delivery_policy_version = 'preview_bootstrap_delivery_policy_v1'
));

CREATE POLICY bootstrap_consumption_owner_insert
ON aria_internal.preview_bootstrap_consumptions
FOR INSERT TO aria_preview_runtime_owner
WITH CHECK (EXISTS (
    SELECT 1 FROM public.preview_publications AS p
    JOIN public.preview_representations AS r ON
        (r.id, r.artifact_version_id, r.account_id, r.project_id) =
        (p.representation_id, p.artifact_version_id, p.account_id, p.project_id)
    WHERE (p.id, p.account_id, p.project_id) =
          (preview_bootstrap_consumptions.publication_id,
           preview_bootstrap_consumptions.account_id,
           preview_bootstrap_consumptions.project_id)
      AND r.transformer_version = 'preview_bootstrap_transformer_v1'
      AND r.delivery_policy_version = 'preview_bootstrap_delivery_policy_v1'
      AND r.status = 'ready' AND p.status = 'ready' AND p.revoked_at IS NULL
      AND p.token_hash IS NOT NULL AND p.issued_at IS NOT NULL
      AND preview_bootstrap_consumptions.consumed_at >= p.issued_at
      AND preview_bootstrap_consumptions.consumed_at < p.expires_at
));

CREATE FUNCTION aria_internal.protect_bootstrap_consumption() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $body$
BEGIN
    RAISE EXCEPTION 'Preview consumption is immutable' USING ERRCODE = '55000';
END;
$body$;
REVOKE ALL ON FUNCTION aria_internal.protect_bootstrap_consumption() FROM PUBLIC;
CREATE TRIGGER trg_bootstrap_consumption_immutable
    BEFORE UPDATE OR DELETE ON aria_internal.preview_bootstrap_consumptions
    FOR EACH ROW EXECUTE FUNCTION aria_internal.protect_bootstrap_consumption();
CREATE TRIGGER trg_bootstrap_consumption_no_truncate
    BEFORE TRUNCATE ON aria_internal.preview_bootstrap_consumptions
    FOR EACH STATEMENT EXECUTE FUNCTION aria_internal.protect_bootstrap_consumption();
```

PK supplies `UNIQUE(publication_id)` and its index; no second random identity/sequence or TTL index.
The existing parent unique `(id, account_id, project_id)` supports the composite FK. PK-first lookup
also bounds a child lookup for that FK to one row. No additional query/index or performance result
is assumed. There are no UPDATE/DELETE policies or write grants beyond INSERT. Protection also
rejects no-op UPDATE and TRUNCATE; no cleanup/down migration removing consumption is designed.

The parent immutable-identity/delete triggers plus RESTRICT FK prevent normal deletion/recreation
of a consumed Publication with the same identity. A newly issued Publication requires its own
independent identity under the existing command contract. Privileged administrators able to drop
tables/disable triggers are outside runtime guarantees; no such operational action is authorized.

## 4. Proposed Preflight — no lock reservation, no consumption

```sql
CREATE FUNCTION aria_internal.preflight_preview_bootstrap(p_hash TEXT) RETURNS JSONB
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = '' SET row_security = on AS $body$
DECLARE result JSONB;
BEGIN
    IF p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$' THEN
        RETURN NULL;
    END IF;
    SELECT pg_catalog.jsonb_build_object(
        'publication_id', p.id, 'account_id', p.account_id, 'project_id', p.project_id,
        'artifact_id', ar.id, 'artifact_version_id', a.id, 'version_no', a.version_no,
        'representation_id', r.id, 'source_hash', r.source_hash,
        'manifest_ref', r.manifest_ref, 'manifest_hash', r.manifest_hash
    ) INTO result
    FROM public.preview_publications AS p
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
    WHERE p.token_hash = p_hash AND p.status = 'ready' AND p.revoked_at IS NULL
      AND p.expires_at > pg_catalog.clock_timestamp()
      AND r.status = 'ready' AND a.status = 'ready' AND a.artifact_hash = r.source_hash
      AND r.transformer_version = 'preview_bootstrap_transformer_v1'
      AND r.delivery_policy_version = 'preview_bootstrap_delivery_policy_v1'
      AND NOT EXISTS (
          SELECT 1 FROM aria_internal.preview_bootstrap_consumptions AS c
          WHERE c.publication_id = p.id
      );
    RETURN result;
END;
$body$;
```

Return is NULL or exactly the ten private metadata keys shown, never packet bytes, raw token or
stored token hash. No enumeration/list operation, arbitrary storage path argument, caller tenant
setting or version fallback exists. Commit/close this read transaction before storage IO.
Preflight may become stale immediately; a positive result authorizes neither delivery nor consume.
Source/packet validation and approved size bounds occur outside DB before the next operation.

## 5. Proposed Consume — Publication lock, full revalidation and unique insert

```sql
CREATE FUNCTION aria_internal.consume_preview_bootstrap(
    p_hash TEXT, p_publication UUID, p_representation UUID,
    p_artifact_version UUID, p_manifest_hash TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = '' SET row_security = on AS $body$
DECLARE b RECORD; v_consumed_at TIMESTAMPTZ; v_inserted BIGINT;
BEGIN
    IF p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$'
       OR p_publication IS NULL OR p_representation IS NULL
       OR p_artifact_version IS NULL OR p_manifest_hash IS NULL
       OR p_manifest_hash !~ '^sha256:[0-9a-f]{64}$' THEN
        RETURN FALSE;
    END IF;

    -- Only one known hash/id target; no caller table, predicate, tenant or profile context.
    PERFORM p.id FROM public.preview_publications AS p
        WHERE p.id = p_publication AND p.token_hash = p_hash FOR UPDATE;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Re-resolve the full graph AFTER acquiring the Publication lock.
    SELECT p.account_id, p.project_id, p.issued_at, p.expires_at INTO b
    FROM public.preview_publications AS p
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
    WHERE p.id = p_publication AND p.token_hash = p_hash
      AND p.representation_id = p_representation
      AND p.artifact_version_id = p_artifact_version
      AND p.status = 'ready' AND p.revoked_at IS NULL AND p.issued_at IS NOT NULL
      AND r.status = 'ready' AND a.status = 'ready' AND a.artifact_hash = r.source_hash
      AND r.transformer_version = 'preview_bootstrap_transformer_v1'
      AND r.delivery_policy_version = 'preview_bootstrap_delivery_policy_v1'
      AND r.manifest_hash = p_manifest_hash;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Wall clock AFTER any lock wait, not transaction-start CURRENT_TIMESTAMP.
    v_consumed_at := pg_catalog.clock_timestamp();
    IF b.expires_at IS NULL OR v_consumed_at >= b.expires_at
       OR v_consumed_at < b.issued_at THEN
        RETURN FALSE;
    END IF;
    INSERT INTO aria_internal.preview_bootstrap_consumptions
        (publication_id, account_id, project_id, consumed_at)
    VALUES (p_publication, b.account_id, b.project_id, v_consumed_at)
    ON CONFLICT (publication_id) DO NOTHING;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RETURN v_inserted = 1;
END;
$body$;
```

Expected IDs/hash are pinning comparisons from Preflight, not client authority. Stored hash binds
the tenant; the composite join checks Project/Artifact/Version/Representation consistently. No
latest resolution, secondary out-of-tenant existence lookup or mixed profile is allowed. Ready
Representation/ArtifactVersion identity/content are protected by existing immutable triggers;
there is no new UPDATE privilege or row lock on those source tables.

Consume locks Publication only, then inserts its ledger row. Existing publish/revoke may acquire
Job -> Publication -> Representation; Consume never subsequently locks Job or Representation, so
it introduces no reverse lock-order edge. No SKIP LOCKED, advisory/session lease or queue retry
substitutes for the final uniqueness constraint. Final observed clock instant must precede expiry;
delivery may finish after expiry under approved One-shot semantics, not live access control.

## 6. Proposed ownership and execution ACLs

PostgreSQL row-locking SELECT needs existing UPDATE permission on at least one parent column.
The reviewed owner already has UPDATE(status) on Publication; this draft adds no such grant and
does not mutate Publication in either helper. No new role or membership is created.

```sql
-- Run in the SAME future approved installation transaction as the preceding definitions.
REVOKE ALL ON FUNCTION aria_internal.preflight_preview_bootstrap(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
    FROM PUBLIC;
ALTER FUNCTION aria_internal.preflight_preview_bootstrap(TEXT)
    OWNER TO aria_preview_runtime_owner;
ALTER FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
    OWNER TO aria_preview_runtime_owner;
GRANT EXECUTE ON FUNCTION aria_internal.preflight_preview_bootstrap(TEXT) TO aria_worker;
GRANT EXECUTE ON FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
    TO aria_worker;

DO $acl$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE aria_internal.preview_bootstrap_consumptions FROM anon;
        REVOKE ALL ON FUNCTION aria_internal.protect_bootstrap_consumption() FROM anon;
        REVOKE ALL ON FUNCTION aria_internal.preflight_preview_bootstrap(TEXT) FROM anon;
        REVOKE ALL ON FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
            FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE aria_internal.preview_bootstrap_consumptions FROM authenticated;
        REVOKE ALL ON FUNCTION aria_internal.protect_bootstrap_consumption() FROM authenticated;
        REVOKE ALL ON FUNCTION aria_internal.preflight_preview_bootstrap(TEXT) FROM authenticated;
        REVOKE ALL ON FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
            FROM authenticated;
    END IF;
END;
$acl$;
```

Existing schema USAGE and exact parent-column privileges/RLS are prerequisites, not permission to
grant schema CREATE, generic SQL, role membership or broader parent SELECT/UPDATE. A future
catalog/actual-role gate must verify effective privileges, function ownership, table ownership,
default/inherited ACLs, FORCE RLS and the two fixed function signatures. Failure means STOP, not
repairing global roles/policies to get PASS. No other runtime/public role gains execution via this
draft; this is not an anonymous direct DB API.

## 7. Transaction, crash and error contract

The following is an application transaction template, NOT a performed execution:

```text
approved request guards -> private Preflight read transaction -> close read transaction
-> read complete bounded packet -> validate Manifest/hash/size and exact immutable bytes
-> BEGIN ISOLATION LEVEL READ COMMITTED
-> consume_preview_bootstrap(exact_preflight_binding)
-> FALSE: end transaction, safe 404, no Preview bytes
-> TRUE: COMMIT; only after confirmed success send those already-verified bytes
```

`TRUE` is provisional SQL success, not an HTTP disclosure permit before commit. Crash/cancel before
commit rolls back ledger insertion and releases row locks. Explicit false/denial leaves no new
effect. A failed or unacknowledged commit sends no Preview bytes and triggers no automatic retry;
if commit actually persisted, replay still finds the consumption. Confirmed commit plus lost or
truncated response leaves consumption terminal: no deletion, fake rollback, reconstruction or
token reissue. A new Publication uses a new identity through the existing explicit recovery flow.

No implicit retry on deadlock, serialization failure, DB timeout or network failure is introduced.
At other isolation levels a serialization failure must also fail closed; never reinterpret it as
a successful consumption. No new lock/statement timeout value or automatic expiration is selected.
Public NULL/FALSE denials map to approved uniform 404; operational DB/commit failures remain a
separate complete-P1 transport error-mapping review, never raw SQL text/errors or an assumption
that consume succeeded. Approved 413/415/422 precede SQL under P3.

Application logs/traces/analytics and DB diagnostics must not capture arguments, token/hash,
Manifest/storage references, private metadata, packet bytes or raw exception context. Only bounded
outcomes, allowed operational correlation IDs and SQLSTATE classes may be retained under the safe
logging contract. No report archive or statement/parameter-logging configuration is changed here;
the future local proof must verify diagnostic redaction independently.

## 8. Review/acceptance matrix — EVERY CASE NOT RUN

| ID | Required actual-role/controlled-DB evidence after separate authorization |
|---|---|
| TC-103SQL01 | Exact four fields/PK/composite FK/RESTRICT enforce one consumption and tenant/project consistency; invalid parent graph rejected |
| TC-103SQL02 | Preflight changes no row and reserves nothing; revoke or expiry between preflight/consume prevents consumption |
| TC-103SQL03 | Two sessions race the same hash/binding: at most one committed TRUE/ledger effect; loser gets no disclosure |
| TC-103SQL04 | Revoke with existing Job -> Publication order races Consume without a reverse edge; committed lock ordering determines the allowed One-shot outcome |
| TC-103SQL05 | Hold Publication lock until expiry, then release: waiting Consume uses post-wait clock and denies |
| TC-103SQL06 | Wrong tenant/project/version/Representation/Manifest comparison and v1/mixed profile return safe denial without secondary existence probes |
| TC-103SQL07 | Transaction rollback, backend death, cancellation and failed commit expose no partial effect; uncertain commit never auto-retries or discloses |
| TC-103SQL08 | Confirmed consume plus response loss remains consumed; replay after 24 hours, Idempotency expiry and claim cleanup cannot resurrect it |
| TC-103SQL09 | Worker direct table reads/writes/TRUNCATE, role escalation and PUBLIC/anon/authenticated execution denied; actual function owner is not a target-table owner/bypass role |
| TC-103SQL10 | UPDATE/DELETE/no-op mutation/TRUNCATE blocked; parent delete/recreation with consumed identity denied; no cleanup function or cascade exists |
| TC-103SQL11 | RLS/FORCE, effective ACLs, qualified references and safe search_path verified with actual aria_worker, not DB owner; existing raw Worker SELECT unchanged |
| TC-103SQL12 | Existing 0102 data/functions/resolution remain v1-only and unchanged; no raw token/hash/private binding/content in error/log/trace evidence |

Review must also resolve the P4 profile names/private packet Manifest and separate additive
publishing/failure SQL before any execution plan. No SQL was parsed against PostgreSQL, installed,
compiled or executed; no migration or runtime code was created. All checks above are planned,
not product/Hosted/Production security acceptance.

## 9. Documentation and existing regression checks — 2026-10-17

Existing `npm test` exited 0: Node/Renderer/Web passed (Web 47/47), API **592 passed / 246 skipped /
2 warnings**, Worker **376 passed / 67 skipped / 1 warning**. Existing deprecation and pytest-cache
permission warnings were not suppressed. `npm run validate`: **23/23 PASS**; `npm run scan:secrets`:
**1,236 publishable text files PASS**; whitespace checks PASS (Git line-ending warning only).
These checks do not parse, compile or execute this proposed SQL, test its effective privileges or
replace a future throwaway-PostgreSQL gate. All TC-103SQL scenarios remain **NOT RUN**. This is a
pending design review, not a completed implementation increment. No commit or push performed.
