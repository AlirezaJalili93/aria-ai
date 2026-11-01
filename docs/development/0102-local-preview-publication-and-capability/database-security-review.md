# 0102 Exact Database Authority Source Review

- Date: 2026-10-12
- Status: **Scoped owner execution approval / Local SQL authority gate PASS / full 0102 PENDING**
- Source authority: owner's 0102 limited database-authority decision; [ADR-089](../../adr/ADR-089-local-preview-publication-and-capability.md).
- [Complete SQL draft](./migration-review.sql), [development record](./development.md), [test report](./test-report.md).
- This is a developer-facing review handoff, not an approved Canonical Drive update.
- The immutable linked SQL snapshot was originally marked NOT APPLIED. Following the owner's
  response to the explicit local execution approval question, its executable statements were
  embedded in Alembic 0040 and applied only to disposable PostgreSQL. Historical source comments
  are not the current execution status. No permission scope or executable SQL was changed.

## Exact objects proposed

1. `public.preview_representations`: UUID identity, account/project/artifact/exact version,
   immutable source hash, fixed transformer/policy versions, preparation status, private
   derivative manifest reference/hash, creator and creation time. Composite source FK with
   RESTRICT; unique account/source-version/transformer/policy tuple. Ready requires complete
   manifest metadata; non-ready forbids it. Ready representation and identities are immutable.
2. `public.preview_publications`: UUID identity, account/project/exact version/representation,
   unique publish Job, creator/time, publication status, revoked time, optional SHA-256 token
   hash/expiry/issued time. Capability fields must all be absent or complete; expiry must exceed
   issuance; token hash is unique. Issuance cannot be rotated/reconstructed; revoke is terminal.
   Composite representation and Job FKs enforce tenant/project/version binding with RESTRICT.
   **No separate capability table:** capability lifecycle belongs to Publication.
3. `aria_internal.preview_execution_claims`: **operational third table**, not a third product
   aggregate. Fixed fields: Job PK, Outbox Event FK, owning backend PID. RESTRICT relations;
   row ownership is replaced only after obtaining the existing Job's session advisory lock.

An active-Job partial unique index covers `(account_id, project_id, payload_ref.representation_id)`
for `job_type=preview_publication` and `queued|running`.

## Ownership and actual privilege proposal

```sql
CREATE ROLE aria_preview_runtime_owner
    NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
    NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT USAGE ON SCHEMA public, aria_internal TO aria_preview_runtime_owner;
```

The migration principal owns all three target tables; the role above owns **only the four
functions below**. No role membership, CREATE privilege, source-table ownership or broad
Worker write/read grant is added. All three new tables enable RLS. The helper role receives:

- SELECT on the two Preview metadata tables.
- Column-limited SELECT on ArtifactVersion, Artifact, Project, Account, Job and Outbox metadata.
- UPDATE Representation `(status, manifest_ref, manifest_hash)` only.
- UPDATE Publication `(status)` only: no token/expiry/creator mutation permission.
- UPDATE Job `(status, started_at, finished_at, error_code, error_detail, attempt_count)` only,
  restricted by an RLS policy to `preview_publication` Jobs.
- SELECT/INSERT/UPDATE/DELETE on the fixed operational claim table only.

Job read privileges include `started_at` and `attempt_count`, needed by UPDATE expressions.
Full column lists and policies are in the SQL draft. Role-specific read policies intentionally
trust the fixed helpers; they are **not a claim of full tenant isolation after Worker compromise**.
The current Worker credential architecture and pre-existing raw SELECT policies are unchanged.

Direct privileges on all three new tables are revoked from PUBLIC/aria_worker and optional
anon/authenticated roles. PUBLIC execution is revoked from each function before runtime grants.
Only aria_worker receives explicit runtime EXECUTE; no Guest/anonymous database role receives it.
Two fixed SECURITY INVOKER triggers protect immutable fields/lifecycle and reject hard delete;
these are not SECURITY DEFINER helpers or callable generic database APIs.

## Four fixed SECURITY DEFINER operations

```text
aria_internal.claim_preview(p_job UUID, p_event UUID) -> JSONB
aria_internal.finalize_preview(p_job UUID, p_event UUID, p_ref TEXT, p_hash TEXT) -> VOID
aria_internal.release_preview(p_job UUID, p_event UUID) -> VOID
aria_internal.resolve_preview(p_hash TEXT) -> JSONB
```

All four set `search_path=''`, use schema-qualified fixed relations, validate NULL/shape,
accept no arbitrary relation/SQL/predicate, change no tenant context, and accept no raw token.

- **Claim:** lock Job -> Publication -> Representation in that order. Revalidate exact
  account/project/source/version/hash, Artifact/Project/Account chain, Job payload and Outbox
  Event/envelope/channel. Acquire session advisory lock, bind claim to current backend PID,
  mark same Job running and preparation states. Completed replay checks ready manifest identity.
- **Finalize:** same lock order; require exact Job/Event/current-backend claim and running Job.
  Repeat full graph/source hash validation, reject revoked Publication, require deterministic
  `preview/<account>/<project>/<version>/<representation>/delivery-manifest.json` reference
  and valid hash. Existing ready Representation must have identical manifest identity. Set
  Representation ready + Publication ready + same Job succeeded in the caller's transaction.
- **Release:** delete only matching Job/Event/current-backend claim; unlock only if that claim
  was actually deleted. No arbitrary claim deletion or other-session release.
- **Resolve:** indexed SHA-256 hash lookup, short `FOR SHARE` lock on Publication **before**
  synchronous ready/expiry/revoke and exact immutable source/tenant/project association checks.
  Expiry uses `pg_catalog.clock_timestamp()` after locking, not an earlier transaction-start time.
  Return controlled
  private binding metadata or NULL, not raw token, customer content or public storage URLs.

Transformation/storage occurs outside short DB transactions. If claim commit is ambiguous,
the adapter must discard/invalidate the connection so a session advisory lock cannot survive
in the connection pool. No additional failure helper or automatic retry is implied.

## Review and execution boundaries

Fresh Alembic upgrade passed on disposable PostgreSQL 16. Actual aria_worker login tests verify
valid operations; direct SELECT/INSERT/UPDATE/DELETE denied on all three new tables; no
helper-owner table ownership or bypass; PUBLIC/Data API EXECUTE denied; cross-bound Job/Event
denied; competing claims rejected; same-session release; atomic finalization rollback; backend
death/reclaim; revoke blocking in-flight finalization; duplicate completion/release; one-time
issuance/replay/conflict/concurrent issue; synchronous expiry; hash-only binding; DB identity/hard
delete protection and active-Job uniqueness. This is **database authority proof only**.

Following explicit owner approval, empty-only downgrade is implemented with table locks before
the emptiness check, exact local object/column-grant removal, and preservation of shared Roles.
Re-upgrade verifies a preserved Role's seven attributes rather than altering it. A two-database
test verifies preservation/reuse and cleanup after the last dependency. The legacy rollback
regression now passes. Fresh authority/rollback harness: 36 passed. Final full PostgreSQL suite:
API 801 passed / 1 skipped; Worker 281 passed / 2 skipped. Prior environmental/fixture failures
and reruns are retained in the report. Full 0102 remains PENDING for storage/Worker/Browser
delivery acceptance, not for an unresolved downgrade contract.

`WORKER-CROSS-TENANT-001` remains OPEN: a compromised shared Worker may call valid helpers for
other tenants' valid Jobs/Publications. Synthetic risk acceptance is not Production acceptance.

Hosted/customer runtime, real Provider, commit/push and full tenant-isolation claims remain
unauthorized. **0102 final status remains PENDING.**

## Preready revocation continuation — 2026-10-13

**Current 2026-10-14 clarification:** PENDING statements above are historical SQL-only subgate
notes. The [final Local/Synthetic report](./test-report.md) now records full scoped acceptance,
including real-file two-Publication reuse and Browser evidence. Exact SQL/roles/grants/RLS are
unchanged. This does not close WORKER-CROSS-TENANT-001 or grant Production/Hosted/customer access.

The four-helper sections above describe the original 0040 authority boundary. The separately
approved fifth failure helper is reviewed in [its immutable SQL source](./failure-helper-review.sql)
and verified through 0041; current execution results are in the [test report](./test-report.md).

The owner-approved preready cancellation is an authenticated Application transaction, not an
additional Worker helper. It adds no SQL migration, owner/Worker column grant, table ownership,
RLS policy or shared-credential redesign. The existing tenant/ownership-filtered Publication
association resolves the Job server-side; only that exact Job is locked, then Publication is
locked and its full payload binding is checked again. Lock order matches claim/finalization.

Only a queued/running Job with allocated/publishing Publication transitions to cancelled.
Publication revocation, Job terminal time and safe idempotency outcome commit or roll back
together. Failed/succeeded/cancelled Jobs retain their previous result. Revoke does not steal
or delete another session's claim. Existing release remains usable; claim/finalization deny
the revoked/cancelled execution. Actual aria_worker in-flight tests and a PostgreSQL-observed
lock race verify both ordering outcomes. This does not establish HTTP or browser acceptance.
