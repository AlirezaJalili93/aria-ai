# ADR-090 P5 — Proposed Bootstrap Consumption SQL Contract

**Status: PENDING OWNER SOURCE REVIEW / NOT COMPILED / NOT EXECUTED.**

**SQL review revision: P5-SQL r2, 2026-10-24.** Owner-approved Installer/pre-commit design is
represented below by proposed guard/assertion text, not approval of this exact SQL or execution.

Date: 2026-10-17. Parent: [ADR-090](ADR-090-controlled-preview-workspace-contract.md).
Scope: Local/Synthetic SQL design only. This Markdown is not a migration, application module,
fixture loader or permission to run any statement. P5 logical model and Option A design are
approved; exact DDL, function signatures, grants and role-owner reuse below are proposals.
P4 contract FROZEN by owner on 2026-10-24; P5 SQL review/full ADR Freeze still PENDING/WAIT.
Runtime, Migration, Hosted/customer use and commit/push NO-GO.

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

**Dependency (owner decision 2026-10-24):** P4's identities and complete delivery-profile contract
are now FROZEN. This does not approve these SQL statements or implementation. Current 0040
CHECKs still allow only v1. This document deliberately does not alter those CHECKs or old claim/
finalize/fail/resolve functions. Approval/application of this consumption design alone cannot make
P1 publishable. Private packet Manifest/integration and additive publishing SQL still need their
own source review; changing either frozen P4 version string requires a new reviewed version,
not a runtime parameter or silent amendment.

## 2. Proposed objects and new authority

| Object / principal | Proposed boundary |
|---|---|
| `aria_internal.preview_bootstrap_consumptions` | Four approved logical fields; append-only; PK is Publication identity |
| Existing `aria_preview_runtime_owner` | Proposed function owner; reuse reviewed NOLOGIN/NOBYPASSRLS owner, not table ownership; ledger SELECT(publication_id) and INSERT of the four fields only |
| Existing `aria_worker` | EXECUTE only on two exact helpers; no ledger SELECT/INSERT/UPDATE/DELETE/TRUNCATE |
| PUBLIC / anon / authenticated | No ledger access or new helper execution |
| Installer | Independently controlled temporary Superuser login for this disposable PostgreSQL only; future separately authorized installation, never Worker/helper/guest; not a final SECURITY DEFINER owner or runtime-test identity |

Owner reuse is proposed explicitly, not silently granted. Its existing Job/Publication rights serve
the reviewed 0102 helper family; this design adds no parent-table, Job or role-membership privileges.
It does not claim a per-function dedicated role or isolation after shared-Worker compromise.
The ledger is not owned by the helper owner and has FORCE RLS. Its definer-owner policies check
the stored tenant/project/profile association; callers cannot set a tenant GUC to authorize a row.
The owner can access eligible P1 rows across tenants inside trusted fixed functions; RLS does not
independently authenticate a request's Capability. The helper hash predicates do that. This is a
limited Local/Synthetic boundary, not a Production shared-credential security assessment.

### Owner-approved Installer / pre-commit direction — 2026-10-24

Installer is not an arbitrary account called Admin: it must be the independently controlled
temporary PostgreSQL Superuser installation identity. Its actual login is supplied out-of-band
for a separately authorized future run, never stored here as a credential or invented role name.
Current and session identity must agree; this design does not grant membership, use SET ROLE or
transfer installer rights to any runtime role. No installer role/login is created by this source.
Helper owner stays NOLOGIN/NOBYPASSRLS, owns only its fixed definer functions among the new
objects, and has no schema CREATE. Worker gains only two named EXECUTEs, no ledger write,
ownership/installation capability or grant option. The Superuser exception permits ownership
transfer without granting CREATE to Helper owner. The invoker-only protection trigger function
may remain owned by Installer; neither SECURITY DEFINER function may.

The installation flow is one transaction: create objects -> assign definer ownership -> remove
PUBLIC/default exposure -> explicit grants -> inspect/assert effective authority -> commit only
after all assertions pass. Post-commit operational-role verification remains independent and
must not be run as Superuser. The following revised SQL is a proposal implementing this approved
design direction, still awaiting exact-source review. It is not a migration or runnable proof.

## 3. Proposed DDL and ledger protection — review text only

Future approved installation must concatenate the SQL review blocks in sections 3, 4, 5, 6 and
6.1 in order, inside the single transaction opened below and closed only after the final assertion.
No block is an independently authorized autocommit installation. PUBLIC/default exposure must not
become committed before the gate. Do not use IF NOT EXISTS/OR REPLACE to trust or overwrite unknown
objects. A future runner must stop/report any statement error and roll back; never swallow an
assertion error or report an aborted transaction as a successful install. No DDL transaction or
database connection has actually been opened for this draft.

```sql
-- NOT EXECUTED. Only after explicit source approval and a separate execution authorization.
BEGIN;
SET LOCAL search_path = pg_catalog;

DO $guard$
DECLARE v_installer OID;
BEGIN
    SELECT r.oid INTO v_installer FROM pg_catalog.pg_roles AS r
    WHERE r.rolname = CURRENT_USER AND r.rolsuper;
    IF v_installer IS NULL OR CURRENT_USER <> SESSION_USER
       OR CURRENT_USER IN ('aria_worker', 'aria_preview_runtime_owner', 'anon', 'authenticated')
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_roles AS r
           WHERE NOT r.rolsuper
             AND pg_catalog.pg_has_role(r.oid, v_installer, 'MEMBER')
       ) THEN
        RAISE EXCEPTION 'Preview installer boundary denied' USING ERRCODE = '42501';
    END IF;
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
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles AS r
        WHERE r.rolname IN ('anon', 'authenticated')
          AND (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb
               OR r.rolreplication)
    ) OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles AS r
        WHERE (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb
               OR r.rolreplication)
          AND pg_catalog.pg_has_role('aria_worker', r.oid, 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'Preview runtime elevation denied' USING ERRCODE = '42501';
    END IF;
    IF pg_catalog.has_schema_privilege('aria_worker', 'aria_internal', 'CREATE')
       OR pg_catalog.has_schema_privilege('aria_worker', 'public', 'CREATE')
       OR pg_catalog.has_schema_privilege('aria_preview_runtime_owner', 'aria_internal', 'CREATE')
       OR pg_catalog.has_schema_privilege('aria_preview_runtime_owner', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Preview schema authority denied' USING ERRCODE = '42501';
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
ALTER FUNCTION aria_internal.preflight_preview_bootstrap(TEXT)
    OWNER TO aria_preview_runtime_owner;
ALTER FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
    OWNER TO aria_preview_runtime_owner;
REVOKE ALL ON FUNCTION aria_internal.preflight_preview_bootstrap(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION aria_internal.consume_preview_bootstrap(TEXT, UUID, UUID, UUID, TEXT)
    FROM PUBLIC;
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
installation must pass the pre-commit catalog gate in 6.1; actual-role tests after commit must
separately verify runtime behavior. Neither replaces the other. Failure means STOP/ROLLBACK, not
repairing global roles/policies to get PASS. No other runtime/public role gains execution via this
draft; this is not an anonymous direct DB API. The final gate fails on unexpected default ACLs
rather than altering defaults or silently revoking unrelated roles.

### 6.1 Proposed pre-commit effective-authority assertion — NOT EXECUTED

This is a fixed catalog assertion for the three new functions and one new table, not a generic
SQL/privilege API. It has no caller parameters, dynamic SQL, runtime grant or durable helper object.
Raw ACL checks cover every grantee, including PUBLIC and installer-default grants. Effective
checks cover non-Superuser LOGIN principals plus the named Worker/helper/guest roles, including
their reachable SET ROLE paths. Unassigned predefined NOLOGIN capability roles such as
pg_read_all_data are not themselves treated as application logins; if a checked principal can
inherit/use or SET ROLE to them, the effective table/column checks still fail. Extra memberships
into Worker/helper/Installer are denied. Existing unrelated NOLOGIN helpers' schema authority is
not rewritten. Installer and other PostgreSQL Superusers remain administrative authorities outside
runtime isolation guarantees; Worker/helper/guest may not be Superuser or reach those privileges.
Checks are a point-in-time installation boundary under trusted administration, not protection
against a malicious Superuser changing roles/ACLs afterward.

```sql
-- LAST installation statement block, in the transaction opened in section 3.
-- NOT EXECUTED / NOT COMPILED. Any exception requires STOP + ROLLBACK.
DO $verify$
DECLARE
    v_installer OID;
    v_owner OID;
    v_worker OID;
    v_ledger OID;
    v_preflight OID;
    v_consume OID;
    v_protect OID;
    r RECORD;
    q RECORD;
    c RECORD;
    s RECORD;
    privilege_name TEXT;
    actual_allowed BOOLEAN;
    expected_allowed BOOLEAN;
BEGIN
    SELECT oid INTO v_installer FROM pg_catalog.pg_roles
    WHERE rolname = CURRENT_USER AND rolsuper;
    SELECT oid INTO v_owner FROM pg_catalog.pg_roles
    WHERE rolname = 'aria_preview_runtime_owner' AND NOT rolcanlogin AND NOT rolinherit
      AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
      AND NOT rolcreaterole AND NOT rolreplication;
    SELECT oid INTO v_worker FROM pg_catalog.pg_roles
    WHERE rolname = 'aria_worker' AND NOT rolsuper AND NOT rolbypassrls
      AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication;
    IF v_installer IS NULL OR v_owner IS NULL OR v_worker IS NULL
       OR CURRENT_USER <> SESSION_USER
       OR CURRENT_USER IN ('aria_worker', 'aria_preview_runtime_owner', 'anon', 'authenticated')
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = v_owner
       ) OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_roles
           WHERE rolname IN ('anon', 'authenticated')
             AND (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)
       ) OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_roles AS a
           WHERE NOT a.rolsuper
             AND pg_catalog.pg_has_role(a.oid, v_installer, 'MEMBER')
       ) THEN
        RAISE EXCEPTION 'Preview final role boundary denied' USING ERRCODE = '42501';
    END IF;

    v_ledger := pg_catalog.to_regclass('aria_internal.preview_bootstrap_consumptions');
    v_preflight := pg_catalog.to_regprocedure(
        'aria_internal.preflight_preview_bootstrap(pg_catalog.text)');
    v_consume := pg_catalog.to_regprocedure(
        'aria_internal.consume_preview_bootstrap(pg_catalog.text,pg_catalog.uuid,pg_catalog.uuid,pg_catalog.uuid,pg_catalog.text)');
    v_protect := pg_catalog.to_regprocedure('aria_internal.protect_bootstrap_consumption()');
    IF v_ledger IS NULL OR v_preflight IS NULL OR v_consume IS NULL OR v_protect IS NULL THEN
        RAISE EXCEPTION 'Preview final objects denied' USING ERRCODE = '42501';
    END IF;
    SELECT relowner, relkind, relrowsecurity, relforcerowsecurity INTO q
    FROM pg_catalog.pg_class WHERE oid = v_ledger;
    IF q.relowner <> v_installer OR q.relkind <> 'r'
       OR NOT q.relrowsecurity OR NOT q.relforcerowsecurity THEN
        RAISE EXCEPTION 'Preview ledger ownership denied' USING ERRCODE = '42501';
    END IF;
    IF (SELECT count(*) FROM pg_catalog.pg_policy WHERE polrelid = v_ledger) <> 2
       OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_policy WHERE polrelid = v_ledger
             AND polname = 'bootstrap_consumption_owner_select' AND polcmd = 'r'
             AND polroles = ARRAY[v_owner] AND polpermissive AND polqual IS NOT NULL
       ) OR NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_policy WHERE polrelid = v_ledger
             AND polname = 'bootstrap_consumption_owner_insert' AND polcmd = 'a'
             AND polroles = ARRAY[v_owner] AND polpermissive AND polwithcheck IS NOT NULL
       ) THEN
        RAISE EXCEPTION 'Preview ledger policies denied' USING ERRCODE = '42501';
    END IF;
    IF (SELECT count(*) FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'aria_internal' AND p.proname IN (
            'preflight_preview_bootstrap', 'consume_preview_bootstrap',
            'protect_bootstrap_consumption')) <> 3 THEN
        RAISE EXCEPTION 'Preview function identity denied' USING ERRCODE = '42501';
    END IF;
    FOR q IN SELECT * FROM pg_catalog.pg_proc
             WHERE oid = ANY(ARRAY[v_preflight, v_consume, v_protect]) LOOP
        IF q.prokind <> 'f' OR q.proleakproof OR q.provolatile <> 'v'
           OR q.proowner <> (CASE WHEN q.oid = v_protect THEN v_installer ELSE v_owner END)
           OR q.prosecdef <> (q.oid <> v_protect)
           OR q.proconfig IS DISTINCT FROM (CASE WHEN q.oid = v_protect
               THEN ARRAY['search_path=""'] ELSE ARRAY['search_path=""', 'row_security=on'] END)
           OR q.prorettype <> (CASE WHEN q.oid = v_preflight
               THEN 'pg_catalog.jsonb'::pg_catalog.regtype
               WHEN q.oid = v_consume THEN 'pg_catalog.bool'::pg_catalog.regtype
               ELSE 'pg_catalog.trigger'::pg_catalog.regtype END) THEN
            RAISE EXCEPTION 'Preview function authority denied' USING ERRCODE = '42501';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.aclexplode(
                COALESCE(q.proacl, pg_catalog.acldefault('f', q.proowner))) AS a
            WHERE a.privilege_type <> 'EXECUTE'
               OR NOT (a.grantee = q.proowner OR
                   (q.oid <> v_protect AND a.grantee = v_worker AND NOT a.is_grantable))
        ) THEN
            RAISE EXCEPTION 'Preview function ACL denied' USING ERRCODE = '42501';
        END IF;
    END LOOP;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS t
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(t.relacl, pg_catalog.acldefault('r', t.relowner))) AS a
        WHERE t.oid = v_ledger AND a.grantee <> v_installer
    ) OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute AS col
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(col.attacl, '{}'::pg_catalog.aclitem[])) AS a
        WHERE col.attrelid = v_ledger AND col.attnum > 0 AND NOT col.attisdropped
          AND NOT (a.grantee = v_installer OR (a.grantee = v_owner AND NOT a.is_grantable
              AND (a.privilege_type = 'INSERT'
                   OR (col.attname = 'publication_id' AND a.privilege_type = 'SELECT'))))
    ) THEN
        RAISE EXCEPTION 'Preview ledger ACL denied' USING ERRCODE = '42501';
    END IF;
    IF (SELECT count(*) FROM pg_catalog.pg_attribute
        WHERE attrelid = v_ledger AND attnum > 0 AND NOT attisdropped) <> 4
       OR EXISTS (SELECT 1 FROM pg_catalog.pg_attribute
           WHERE attrelid = v_ledger AND attnum > 0 AND NOT attisdropped
             AND attname NOT IN ('publication_id', 'account_id', 'project_id', 'consumed_at'))
       OR (SELECT count(*) FROM pg_catalog.pg_trigger
           WHERE tgrelid = v_ledger AND NOT tgisinternal) <> 2
       OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger
           WHERE tgrelid = v_ledger AND tgname = 'trg_bootstrap_consumption_immutable'
             AND tgfoid = v_protect AND tgenabled = 'O' AND tgtype = 27)
       OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger
           WHERE tgrelid = v_ledger AND tgname = 'trg_bootstrap_consumption_no_truncate'
             AND tgfoid = v_protect AND tgenabled = 'O' AND tgtype = 34) THEN
        RAISE EXCEPTION 'Preview ledger protection denied' USING ERRCODE = '42501';
    END IF;

    FOR r IN SELECT oid, rolname FROM pg_catalog.pg_roles
             WHERE NOT rolsuper AND (rolcanlogin OR oid IN (v_owner, v_worker)
                                    OR rolname IN ('anon', 'authenticated')) LOOP
        IF (r.oid <> v_owner AND pg_catalog.pg_has_role(r.oid, v_owner, 'MEMBER'))
           OR (r.oid <> v_worker AND pg_catalog.pg_has_role(r.oid, v_worker, 'MEMBER'))
           OR EXISTS (
               SELECT 1 FROM pg_catalog.pg_roles AS a
               WHERE (a.oid = r.oid OR pg_catalog.pg_has_role(r.oid, a.oid, 'SET'))
                 AND (a.rolsuper OR a.rolbypassrls OR a.rolcreatedb
                      OR a.rolcreaterole OR a.rolreplication)
           ) THEN
            RAISE EXCEPTION 'Preview effective role denied' USING ERRCODE = '42501';
        END IF;
        FOREACH privilege_name IN ARRAY ARRAY[
            'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles AS a
                WHERE (a.oid = r.oid OR pg_catalog.pg_has_role(r.oid, a.oid, 'SET'))
                  AND pg_catalog.has_table_privilege(a.oid, v_ledger, privilege_name)) THEN
                RAISE EXCEPTION 'Preview effective table ACL denied' USING ERRCODE = '42501';
            END IF;
        END LOOP;
        FOR c IN SELECT attname, attnum FROM pg_catalog.pg_attribute
                 WHERE attrelid = v_ledger AND attnum > 0 AND NOT attisdropped LOOP
            FOREACH privilege_name IN ARRAY ARRAY['SELECT','INSERT','UPDATE','REFERENCES'] LOOP
                expected_allowed := r.oid = v_owner AND (privilege_name = 'INSERT'
                    OR (privilege_name = 'SELECT' AND c.attname = 'publication_id'));
                SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles AS a
                    WHERE (a.oid = r.oid OR pg_catalog.pg_has_role(r.oid, a.oid, 'SET'))
                      AND pg_catalog.has_column_privilege(
                          a.oid, v_ledger, c.attnum, privilege_name)) INTO actual_allowed;
                IF actual_allowed IS DISTINCT FROM expected_allowed OR EXISTS (
                    SELECT 1 FROM pg_catalog.pg_roles AS a
                    WHERE (a.oid = r.oid OR pg_catalog.pg_has_role(r.oid, a.oid, 'SET'))
                      AND pg_catalog.has_column_privilege(a.oid, v_ledger, c.attnum,
                          privilege_name || ' WITH GRANT OPTION')) THEN
                    RAISE EXCEPTION 'Preview effective column ACL denied' USING ERRCODE = '42501';
                END IF;
            END LOOP;
        END LOOP;
        FOR q IN SELECT oid FROM pg_catalog.pg_proc
                 WHERE oid = ANY(ARRAY[v_preflight, v_consume, v_protect]) LOOP
            expected_allowed := q.oid <> v_protect AND r.oid IN (v_owner, v_worker);
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles AS a
                WHERE (a.oid = r.oid OR pg_catalog.pg_has_role(r.oid, a.oid, 'SET'))
                  AND pg_catalog.has_function_privilege(a.oid, q.oid, 'EXECUTE'))
                INTO actual_allowed;
            IF actual_allowed IS DISTINCT FROM expected_allowed THEN
                RAISE EXCEPTION 'Preview effective function ACL denied' USING ERRCODE = '42501';
            END IF;
        END LOOP;
        IF r.oid IN (v_owner, v_worker) THEN
            FOR s IN SELECT oid FROM pg_catalog.pg_namespace
                     WHERE nspname IN ('public', 'aria_internal') LOOP
                IF NOT pg_catalog.has_schema_privilege(r.oid, s.oid, 'USAGE')
                   OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles AS a
                       WHERE (a.oid = r.oid OR pg_catalog.pg_has_role(r.oid, a.oid, 'SET'))
                         AND (pg_catalog.has_schema_privilege(a.oid, s.oid, 'CREATE')
                              OR pg_catalog.has_schema_privilege(
                                  a.oid, s.oid, 'USAGE WITH GRANT OPTION'))) THEN
                    RAISE EXCEPTION 'Preview effective schema ACL denied' USING ERRCODE = '42501';
                END IF;
            END LOOP;
        END IF;
    END LOOP;
END;
$verify$;

-- Reached only if every check passed. There is no exception-swallowing branch.
COMMIT;
```

`tgtype` values above are fixed catalog bitmasks for the reviewed BEFORE ROW UPDATE/DELETE and
BEFORE STATEMENT TRUNCATE triggers, not caller flags. Catalog tests do not execute the policies,
triggers or helpers as Worker and cannot establish actual RLS behavior. Superuser-owned ledger
and invoker trigger are installation artifacts; the two runtime SECURITY DEFINER owners must be
the restricted role, never Installer. Inherited/default ACLs are inspected on the newly created
objects, not reset globally. No post-commit check may substitute for this in-transaction gate.
All proposed assertion SQL remains uncompiled/unexecuted and requires exact source review.

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
| TC-103SQL13 | Installer is an independent temporary Superuser session; Worker/helper/guest and non-Superuser installation fail without giving Helper owner schema CREATE or Installer membership |
| TC-103SQL14 | Unexpected PUBLIC/default/column grants, inherited privileges or reachable SET ROLE authority abort the install transaction before commit; no global role/default-ACL repair |
| TC-103SQL15 | Final runtime SECURITY DEFINER owner is the restricted role, not Installer/table owner; no Worker ownership/grant option/direct ledger privilege; safe function settings and FORCE RLS inspected before commit |
| TC-103SQL16 | Any final catalog assertion failure rolls back all new objects/grants; post-commit actual-role negative/positive tests remain separate and are not replaced by Superuser catalog inspection |

Review must also resolve the P1 private packet Manifest/integration and separate additive
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

## 10. Historical independent engineering source review — 2026-10-24, before r2

This records the earlier source review and its then-open SR-P5-01/02 findings. Section 11 records
the subsequent owner decision and proposed r2 corrections. Statements below about unchanged SQL
refer to that earlier review, not the current r2 source; none is an execution/acceptance claim.

**Review mode:** read-only examination of the proposed SQL text and existing repository source,
not a PostgreSQL parser/compiler, connection, migration or actual-role test. The owner approved P4
at contract level and authorized this independent P5 review, **not P5 SQL approval or execution**.
All fenced SQL statements above remain unchanged. No new executable assertion, helper, role,
grant, policy or test was added. Existing sections 1–8 remain the proposed source under review;
this section does not silently amend their executable installation sequence.

Compared with 0038's ready ArtifactVersion immutability, 0040's composite parent keys, parent
privileges/RLS and immutable Publication/Representation identities, 0041's separate failure helper,
and the current repository's scoped Job -> Publication revoke lock order. No fresh Drive read or
global Worker credential/RLS redesign is part of this review.

### Static observations — reasoned expectations, not test PASS

| Area | Source observation | Limit / required existing acceptance case |
|---|---|---|
| Stored authority and exact graph | Both helpers use a canonical hash and fixed composite joins; Consume derives account/project from the stored graph, not caller tenant input | Valid-Capability + stored-binding decision preserved; TC-103SQL01/06/11 still NOT RUN |
| Durable single consumption | Ledger PK is publication_id; Consume takes its Publication lock, then uses the PK conflict target and returns true only for one inserted row | Two callers cannot both retain a committed ledger row for the same PK; actual lock/conflict behavior and failed commits require TC-103SQL03/07, not proof by inspection |
| Revoke and expiry boundary | Final revalidation follows the Publication lock; server wall-clock observation follows any lock wait; ready Representation/ArtifactVersion cannot normally change content/binding | Revoke taking the same Publication lock has an ordered outcome; no reverse Job lock requested by Consume; TC-103SQL02/04/05 still required |
| Commit and response | TRUE is provisional; response follows confirmed outer commit only; failed/unknown commit discloses no bytes and has no automatic retry/reissue | Functions do not independently commit; caller/driver behavior and response loss still require TC-103SQL07/08 and the future Application/HTTP gate |
| Retention and immutability | No TTL/cleanup link, UPDATE/DELETE policy or runtime mutation grant; RESTRICT FK plus immutable parent/ledger triggers; TRUNCATE has a separate rejecting trigger | RLS alone does not govern TRUNCATE; effective privileges and trigger behavior require TC-103SQL09/10/11 |
| New privileges | Owner receives ledger SELECT(publication_id) plus explicit four-column INSERT; Worker receives only two named EXECUTEs; no parent privilege broadened | SELECT(publication_id) is needed by the conflict target and Preflight; inspect effective ACLs, not only the visible GRANT text; see SR-P5-01 |
| Definer safety | Empty search_path, schema-qualified persistent relations, fixed signatures and no dynamic SQL/tenant-context mutation | Owner is restricted but has existing cross-tenant parent SELECT policies; this does not establish isolation after shared Worker compromise; no Production approval |
| Legacy compatibility | Existing 0040 CHECKs and helpers remain exact v1-only; no code dispatch or profile widening appears in P5 | P4 contract Freeze does not make this source publishable; private Manifest/integration and separately reviewed additive publishing/failure SQL remain required |

These observations identify no new duplicate-consumption path under the stated fixed-function,
immutable-parent, READ COMMITTED and confirmed-commit assumptions. They do not establish compiled
SQL validity, actual privileges, throughput, deadlock freedom across every caller or full runtime
security. The reused role remains a proposal awaiting owner review, not a newly approved owner.

### Installation clarifications requiring resolution before SQL acceptance

**SR-P5-01 — Effective-authority checks must not leave an install/verification window.**
Section 6 requires catalog/actual-role gates, but the review source does not yet spell out an
executable final **pre-commit catalog assertion**. The explicit REVOKEs remove PUBLIC and named
roles; they do not by themselves prove absence of grants to another role inherited from installer
default privileges, unexpected memberships, schema authority or unintended ownership. Proposed
clarification: verify the new table/function owners, FORCE RLS, role attributes/membership and
effective table/column/function/schema authority within the same installation transaction, before
commit; any mismatch aborts/rolls back rather than repairing global defaults or expanding roles.
Only the already reviewed administrative installation principal may be excepted from runtime
access restrictions. Subsequent actual aria_worker tests are a separate post-install test gate
after execution is separately authorized. This is a source-completeness concern, not evidence
that such an unexpected grant currently exists; no database catalog was queried.

**SR-P5-02 — Name the permitted installation authority without granting runtime schema CREATE.**
The proposed ALTER FUNCTION OWNER statements need an explicit installation prerequisite. PostgreSQL
normally requires the caller to be able to SET ROLE to the new owner and the new owner to have
CREATE on that schema; a superuser may change ownership without those ordinary restrictions.
The existing 0040 source already uses ownership transfer; that history does not authorize a new
elevation or prove the next selected installation principal can do it. The proposed source guards
reject installation as the helper owner but do not explicitly reject runtime principals as the
new ledger's implicit owner. Proposed clarification: independently reviewed installation identity
must not be aria_worker, the helper owner, or public/guest runtime roles; preserve the owner
separation and no-CREATE runtime boundary, and fail if the authorized installer cannot transfer
ownership. Do not grant schema CREATE or role membership to the helper/Worker to make installation
pass. No privileged connection, principal selection, SET ROLE, new guard SQL or grant is performed
or authorized by this finding.

Both clarifications are recommendations for the next owner-reviewed SQL revision. They do not
change the four-field model, capability transport, product lifecycle, retry policy or retention.
No corrected DDL/assertion is claimed to exist until its source is separately prepared/reviewed;
the present SQL remains PENDING, NOT COMPILED / NOT EXECUTED. No installation or future release
may be presented as verified merely because the static review was completed.

### Technical references and verification boundary

Primary PostgreSQL 16 references checked 2026-10-24:

- [INSERT privileges/conflict target](https://www.postgresql.org/docs/16/sql-insert.html): explicit
  column INSERT and SELECT on conflict-target/read columns; no inferred whole-table SELECT grant.
- [Transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html): lock waits,
  READ COMMITTED snapshots and DO NOTHING conflict behavior; other isolation errors fail closed.
- [Row security](https://www.postgresql.org/docs/16/ddl-rowsecurity.html): RLS is additional to ACLs;
  owners/bypass roles and whole-table operations require independent checks.
- [Definer function installation](https://www.postgresql.org/docs/16/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY):
  function creation/ACL restriction in one transaction; no default PUBLIC execution window.
- [Ownership transfer prerequisites](https://www.postgresql.org/docs/16/sql-alterfunction.html):
  distinguish installer authority from the least-privilege runtime function owner.

The PostgreSQL skill guided minimum new privilege, short final transactions and explicit lock-order
review only; its examples did not authorize arbitrary settings, timeout values or role redesign.
TC-103SQL01..12 all remain **NOT RUN**. P4 contract is FROZEN; P5 SQL owner review PENDING;
full ADR-090 WAIT; Runtime/SQL execution/Migration/Hosted/customer use and commit/push NO-GO.

Documentation/regression verification for this review, 2026-10-24: `npm test` exit 0; existing
Node/Renderer/Web stages passed (Web 47/47), API **592 passed / 246 skipped / 2 warnings in 33.42s**,
Worker **376 passed / 67 skipped / 1 warning in 24.38s**. Deprecation/cache-permission warnings were
not suppressed. `npm run validate` **23/23 PASS**, Secret Scan **1,237 files PASS**, diff whitespace
checks PASS (line-ending warnings only). Text-only comparison against HEAD confirms all proposed
SQL blocks unchanged. No database/compiler/Browser Proof or new P5 executable case was run;
TC-103SQL01..12 remain NOT RUN. Existing uncommitted MVP assessment report was not modified.
No commit/push or external-system mutation; P5 acceptance remains PENDING OWNER REVIEW.

## 11. Owner Installer decision and proposed P5-SQL r2 — 2026-10-24

Authority: owner's explicit **P5 INSTALLATION AUTHORITY — APPROVED FOR SQL CONTRACT DESIGN ONLY**.
REQ-10323 in the parent ADR traces this revision. SR-P5-01/02 now have approved design direction,
not executable acceptance: independent temporary Superuser Installer, no schema CREATE or
installation/membership privilege transferred to Worker/Helper owner, and an in-transaction
effective-authority gate before any commit. Exact DDL/helper/grant source still awaits review.

Changes are confined to this Markdown and parent ADR status/traceability. Sections 3 and 6/6.1
propose the session guard, ownership/ACL ordering, fixed catalog assertions and final COMMIT.
No temporary SQL file, migration or runnable assertion test was created. The preflight, consume
and ledger-protection function definitions retain their prior proposed bodies; no data path,
Capability input, lifetime, error mapping, retention or parent-table privilege was broadened.
Unexpected defaults/membership/schema authority cause STOP/ROLLBACK, not automatic global repair.

The gate inspects actual newly created object ACLs (including installer default grants), all raw
grantees, effective privileges for operational identities and reachable SET ROLE paths, final
ownership, function settings and ledger RLS/protection metadata. It does not prove policy predicates
execute correctly or establish isolation after shared Worker/Superuser compromise. Actual-role
positive/negative checks remain TC-103SQL01..16 **NOT RUN**. These sixteen are planned cases, not
sixteen passing tests. A failed final assertion must prevent installation commit; future authorized
runner error handling and actual rollback still require their own execution evidence.

Technical references checked for this design: PostgreSQL 16
[ownership transfer](https://www.postgresql.org/docs/16/sql-alterfunction.html),
[privilege inspection / ACL defaults](https://www.postgresql.org/docs/16/functions-info.html),
[role membership and SET ROLE](https://www.postgresql.org/docs/16/role-membership.html),
[function catalog](https://www.postgresql.org/docs/16/catalog-pg-proc.html) and
[policy catalog](https://www.postgresql.org/docs/16/catalog-pg-policy.html).
The PostgreSQL skill informed ACL/membership inspection and least privilege only; it does not
approve this SQL, select an Installer credential or authorize a connection, runtime or migration.

**Current status:** proposed r2 source complete for review, **NOT COMPILED / NOT EXECUTED**;
P5 exact SQL PENDING OWNER SOURCE REVIEW; P4 contract FROZEN; full ADR-090 WAIT. Runtime,
SQL execution/Migration, Browser Proof, Hosted/customer use and commit/push remain NO-GO.

Documentation/regression verification for r2: `npm test` exit 0; existing Node/Renderer/Web stages
passed (Web 47/47), API **592 passed / 246 skipped / 2 warnings in 33.81s**, Worker **376 passed /
67 skipped / 1 warning in 21.88s**. Existing deprecation/cache-permission warnings were not
suppressed. Service-test environment variables were absent; no PostgreSQL/Redis integration or
Browser Proof was enabled. `npm run validate` **23/23 PASS**, Secret Scan **1,237 files PASS**,
and diff whitespace checks PASS (line-ending warnings only). Text-only comparison against HEAD
confirms the three fixed function definitions are identical, not all SQL blocks: installer/ACL
blocks were intentionally revised as authorized. Only the two tracked ADR Markdown files differ;
the pre-existing uncommitted MVP report is preserved. No new SQL case was compiled/executed,
no runtime/migration source changed, and no commit/push/external-system write occurred.
