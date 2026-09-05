# Migrations

Alembic is the accepted migration owner under ADR-008. `DATABASE_URL` is required at execution and
is never stored in this directory.

```text
0000_extensions → 0001_identity_projection → 0001_identity_access_hardening
→ 0002_projects → 0003_project_create_idempotency → 0004_context_sources
→ 0005_jobs_outbox → 0006_idempotency_records → 0007_usage_records
→ 0008_context_items
```

M001 creates `accounts`, `profiles`, and `account_memberships` and enables RLS with no policy or Data
API access, so the public schema is deny-by-default for non-owner roles. The follow-up M001
hardening revision enables RLS on Alembic's version table, revokes provider-created `anon` and
`authenticated` privileges from the current tables when those roles exist, and removes matching
default privileges owned by the migration role. Supabase also has provider-owned
`supabase_admin` defaults that the migration role cannot modify. Until the documented M010 policy
step, every new Aria public-table migration must therefore explicitly revoke current
`anon`/`authenticated` table privileges. Applied shared-environment revisions are immutable.

Logical product migration numbers and physical Alembic revision numbers intentionally differ after
incremental hardening revisions. `0005_jobs_outbox` implements logical M008. The current Detailed
Data Dictionary vocabulary and the supersede decision are recorded in
[ADR-013](../../../docs/adr/ADR-013-jobs-outbox-persistence.md).

`0006_idempotency_records` adds the reusable 24-hour request-result reservation store used first by
Text Context ingestion. Its actor-aware scope and request fingerprint contract are recorded in
[ADR-014](../../../docs/adr/ADR-014-text-context-ingestion.md).

`0007_usage_records` implements the S1-G05 Usage Ledger portion of logical M009. It creates the
append-only table and the non-bypass `aria_worker` runtime role, grants that role only `INSERT`,
keeps API/Data API roles denied, and uses `ON DELETE RESTRICT` for Account/Project/Job history.
Provider price persistence remains deferred to S1-G06. The role is retained on downgrade because
it may pre-exist or receive credentials outside migration ownership; the Ledger policy and table
grant are removed before the table is dropped. See
[ADR-024](../../../docs/adr/ADR-024-usage-ledger-and-worker-role.md).

`0008_context_items` implements logical M004 after the already-delivered physical migrations. It
uses integer `context_version`, plural JSONB `source_refs`, four-state review status, restrictive
Account/Project/Profile foreign keys, tenant-first indexes and deny-by-default Data API access.
Element-level provenance is resolved against ready same-tenant Source Versions before persistence;
the conflict supersede and exact boundary are recorded in
[ADR-025](../../../docs/adr/ADR-025-context-item-provenance-contract.md).
