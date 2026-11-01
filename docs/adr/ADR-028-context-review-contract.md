# ADR-028: Current Context Review Contract

- **Status:** Accepted
- **Date:** 2026-09-06
- **Story:** S1-H04 — Structured Context Review UI/API
- **Supersedes:** H01 omission of a mutation timestamp for Context Items

## Context

The approved H04 contract adds human review of the current Project Context version. Review must
be tenant-authorized, preserve provenance during edits, and distinguish a stale write from an
invalid state transition. The existing Context Item schema had `created_at` but no mutable-row
timestamp, so it could not support the approved optimistic-concurrency contract.

## Decision

- Add database-owned `updated_at TIMESTAMPTZ NOT NULL` to `context_items`, maintained by the shared
  `BEFORE UPDATE` timestamp trigger.
- Read only the Project's `current_context_version`; ordinary queries are tenant-scoped and exclude
  soft-deleted Projects. `source_id` filtering matches an actual `source_refs` element.
- Expose `GET /api/v1/projects/{project_id}/context-items` with canonical item/status filters and
  opaque keyset pagination `(created_at,id)` descending, default 20 and maximum 100.
- Expose `PATCH /api/v1/projects/{project_id}/context-items/{item_id}` with `confirm`, `reject`,
  and `edit`. Only `proposed` items are mutable. `edit` changes content only, keeps `source_refs`
  and status `proposed`, and does not claim semantic source re-validation.
- Require `expected_updated_at`; a mismatch is `409 VERSION_CONFLICT`, while a non-proposed item
  is `409 INVALID_CONTEXT_ITEM_STATE`. Missing or cross-tenant resources use safe `404`.
- Active owner/admin/member Memberships may read and review through backend authorization.
- UI presents the six canonical item types; “Missing Information” is the `unknown` label. Delete,
  regenerate, processing-state integration and semantic re-validation remain deferred.

## Consequences

PostgreSQL remains the concurrency authority and provenance remains visible to reviewers. Review
events are structured and identifier-only; content, raw Source References, JWTs and callback
secrets are not logged. The web review route is RTL-first and uses the existing design tokens.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H04
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — §12
- [Access Control Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit)
- [UX Information Architecture & Screen Specification v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — SCR-10
- Owner-approved H04 contract dated 2026-09-06
