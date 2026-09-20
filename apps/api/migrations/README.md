# Migrations

Alembic is the accepted migration owner under ADR-008. `DATABASE_URL` is required at execution and
is never stored in this directory.

```text
0000_extensions → 0001_identity_projection → 0001_identity_access_hardening
→ 0002_projects → 0003_project_create_idempotency → 0004_context_sources
→ 0005_jobs_outbox → 0006_idempotency_records → 0007_usage_records
→ 0008_context_items → 0009_usage_repair_number → 0010_context_item_review
→ 0011_requirements → 0012_requirement_generation → 0013_requirement_crud
→ 0014_gaps → 0015_gap_detection → 0016_clarifications → 0017_scope_drafts
→ 0018_scope_versions
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

`0011_requirements` implements logical M005 with an integer Context Version, mandatory category,
title/description and explicit priority, four-state soft-deactivation lifecycle, H01-compatible
Source References, restrictive tenant/creator foreign keys, database-owned timestamps, RLS and
fail-closed Data API privileges. Application rejects missing/future Project Context Versions and
invalid provenance before persistence. The conflict resolution is recorded in
[ADR-030](../../../docs/adr/ADR-030-requirement-domain-contract.md).

`0012_requirement_generation` extends M005 for S1-I02 with an explicit unsupported flag,
provider-output duplicate key and a non-unique Job reference plus tenant-first replay index. It
does not add a conflict or Gap table. Requirement rows and safe conflict Outbox events commit in
one transaction; exact Context snapshot and merge rules are recorded in
[ADR-031](../../../docs/adr/ADR-031-requirement-generation-contract.md).

`0013_requirement_crud` adds nullable `acceptance_note` and the tenant-first descending pagination
index used by S1-I03. It preserves the existing RLS/grants and four-state soft lifecycle; public
commands never hard-delete Requirement rows. See
[ADR-032](../../../docs/adr/ADR-032-requirement-crud-contract.md).

`0014_gaps` implements the J01 Gap Domain. `0015_gap_detection` extends it for J02-A with nullable
generation fields (preserving J01 rows), normalized affected-Requirement links, same-tenant
composite foreign keys, same-Context-snapshot enforcement and fail-closed Data API privileges.
The exact dual-revision snapshot, replay and Critical-rule deferral are recorded in
[ADR-036](../../../docs/adr/ADR-036-gap-detection-foundation.md).

`0017_scope_drafts` implements S1-K01 as a tenant-scoped, mutable, version-bound Working Draft.
Content is strict `scope_content_schema_v1` JSONB; all canonical sections are structurally required
but may be empty. Drafts are unique per Project/Context Version, historical drafts are protected by
Application policy, and readiness/revision state remains outside K01. See ADR-041.

`0018_scope_versions` implements S1-K05 as an immutable, tenant-scoped snapshot of a ready Scope
Draft. Snapshot hashes use `scope_snapshot_canonicalization_v1`; payload and lineage are protected
by a database trigger, while lifecycle status remains a separately controlled projection. The
table uses restrictive tenant foreign keys, safe public-schema grants and summary/detail indexes.
See ADR-045.

`0021_txt_parser_worker_access` adds only the read/update authority required by the controlled TXT
Parser consumer. `aria_worker` can read and update Jobs, Context Sources and Source Versions and can
read the referenced Outbox row; it cannot insert or delete those records. Session advisory locking,
atomic finalization and crash-recovery semantics are recorded in ADR-051. No Relay Scheduler is
introduced.

`0022_context_source_management` adds immediate-parent retry lineage to Jobs, enforces at most one
direct child per failed Job and one queued/running parser Job per Source Version, and extends the
Source cursor index with the stable UUID tie-breaker. Source archive remains status-based and does
not remove Versions or Storage objects. See ADR-052.

`0023_provider_price_versions` completes logical M009 with a global immutable price catalog,
deterministic effective-time uniqueness, read-only Worker authority and the exact composite Price
identity referenced by new Usage records. The Usage FK and cached-token subset check are added as
`NOT VALID` so they protect every new write while preserving historical rows without fabricated
price backfills. The catalog is intentionally empty until G02/G03 approve a real Provider. See
ADR-054.
