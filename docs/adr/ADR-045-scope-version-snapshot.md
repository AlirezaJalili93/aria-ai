# ADR-045 — Scope Version Snapshot

- **Status:** Accepted — owner approval received 2026-09-12
- **Story:** S1-K05 — Scope Version Snapshot
- **Extends:** ADR-041 Scope Draft Model; ADR-042 Scope Readiness Policy; ADR-044 Scope Draft Editor

## Decision

K05 freezes the exact current, ready Scope Draft into a new immutable snapshot after an explicit
active-Member command. The request carries `expected_draft_updated_at` and a mandatory
`Idempotency-Key`. Resolution order is idempotency replay/conflict, current Project/Draft lookup,
Draft CAS, K02 readiness, `scope_content_schema_v1` validation, canonicalization, hash, semantic
duplicate detection, atomic version allocation and insert.

A missing current Draft is safe `404 RESOURCE_NOT_FOUND`; a stale Draft is
`409 VERSION_CONFLICT`; unresolved Critical Gaps are `422 CRITICAL_GAPS_OPEN`; and a new key whose
snapshot equals the latest Version is `409 SCOPE_VERSION_UNCHANGED`. The same unexpired key and
same input replays the original successful response before duplicate detection; a different input
with that key is `409 IDEMPOTENCY_CONFLICT`.

## Canonical snapshot and hash

`snapshot_data` is a complete validated copy of the Draft's `scope_content_schema_v1`, including
all lineage traces. `scope_snapshot_canonicalization_v1` serializes the JSON as UTF-8, sorts object
keys lexicographically, emits no insignificant whitespace, preserves array order and injects no
timestamp or version metadata. The v1 schema contains no numeric values; future numeric support
requires a new canonicalization contract.

`snapshot_hash` is `sha256:<64 lowercase hexadecimal characters>` over the complete canonical
snapshot bytes. The full hash and snapshot content are excluded from operational logs.

## Persistence and lifecycle

`scope_versions` stores `id`, direct tenant/project keys, strictly increasing `version_no`, exact
`context_version`, `status`, `snapshot_data`, `snapshot_hash`, `created_by` and `created_at`.
PostgreSQL enforces restrictive Account/Project/Creator references,
`UNIQUE(project_id,version_no)`, hash/status checks, tenant-leading indexes and an immutability
trigger. A Project row lock serializes allocation. K05 creates only `awaiting_approval`.

Snapshot payload, hash, context/version identity, lineage, creator and creation time are immutable;
deletion is forbidden. `status` is a separately controlled lifecycle projection and may change
only through a future explicitly contracted lifecycle operation. K05 exposes no status mutation.
This supersedes the ambiguous statement that approval cannot mutate any ScopeVersion field:
approval cannot mutate payload or hash, while lifecycle status is a controlled projection.

RLS is enabled and public/Data API roles retain no direct grants under the accepted fail-closed
pre-M010 architecture. Application authorization and every repository query remain tenant-scoped;
RLS/grant catalog and cross-tenant tests verify isolation. No unapproved direct Data API policy is
introduced by K05.

## API and observability

- `POST /api/v1/projects/{project_id}/scope/versions` creates/replays a Version summary.
- `GET /api/v1/projects/{project_id}/scope/versions` returns paginated summaries only.
- `GET /api/v1/projects/{project_id}/scope/versions/{version_no}` adds `snapshot_data`.
- No PATCH or DELETE route exists.

Public summaries contain `version_no`, `context_version`, lifecycle `status`, `snapshot_hash`,
content `schema_version` and `created_at`. Internal `created_by` is not exposed. Missing and
cross-tenant resources share safe not-found behavior.

Operational events are `scope_version.created`, `scope_version.unchanged_rejected`,
`scope_version.version_conflict` and `scope_version.creation_failed`. Product Analytics uses
`scope_version_saved`. Events contain only safe identifiers and version metadata, never snapshot,
trace, content or full hash.

## Explicit exclusions

Share links, guest access, approval records, lifecycle transition rules, section regeneration and
Snapshot deletion are outside K05.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K05; synchronized 2026-09-12.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Scope Versions; synchronized 2026-09-12.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Scope API; synchronized 2026-09-12.
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Member freeze/read and immutable Versions; synchronized 2026-09-12.
- [PRD v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-07-05; synchronized 2026-09-12.
- [AI Workflow Specification](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-05 freeze boundary; synchronized 2026-09-12.
- Owner-approved K05 refinements dated 2026-09-12.
