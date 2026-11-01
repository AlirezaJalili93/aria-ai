# ADR-079 — Authenticated Scope Revision Command

- **Status:** Accepted
- **Date:** 2026-10-05
- **Increment:** `0092-authenticated-scope-revision`
- **Extends:** ADR-044, ADR-045, ADR-078

## Context

ADR-078 records an immutable public Change Request and moves its exact Scope Version to
`changes_requested`, but intentionally does not change the authenticated Draft or create a new
Version. K04 already owns manual Draft editing and K05 owns immutable Scope snapshots. A distinct
authenticated command is required to consume one Change Request, snapshot the edited Draft and
preserve explicit revision lineage without letting the generic K05 route bypass that lineage.

## Decision

- Add `POST /api/v1/projects/{project_id}/scope/versions/{version_no}/revisions` with mandatory
  `Idempotency-Key` and exact body `change_request_id + expected_draft_updated_at`.
- Active Owner/Admin/Member authority uses the existing tenant context. Missing, cross-tenant or
  non-visible Project, target Version or Change Request remains `RESOURCE_NOT_FOUND`.
- Lock Project, resolve maximum `version_no`, lock the target Version, exact Change Request and
  current Draft, then revalidate CAS, exact Context Version, K02 readiness and K01 schema inside one
  transaction. No selection of an implicit latest Context is allowed.
- A valid command creates N+1 as `awaiting_approval`, persists both
  `revision_of_scope_version_id=N.id` and `change_request_id`, and moves N from
  `changes_requested` to `superseded` in the same transaction.
- Revision lineage is all-or-none, immutable, tenant/project constrained and a Change Request can
  be consumed only once. Initial Versions retain both lineage fields as NULL.
- `expected_draft_updated_at` mismatch is `VERSION_CONFLICT`. Invalidated revision state,
  relationship, latest Version or Context binding is `SCOPE_REVISION_STALE`. An unchanged
  canonical snapshot is `SCOPE_VERSION_UNCHANGED`; unresolved Critical Gaps remain
  `CRITICAL_GAPS_OPEN`.
- First success returns 201. Exact replay returns the same N+1 with 200 and `replayed=true` before
  stale-state evaluation. Changed semantics return `IDEMPOTENCY_CONFLICT`.
- The generic K05 create route returns `SCOPE_REVISION_REQUIRED` whenever the latest Version is
  `changes_requested`.
- Historical Share Links remain bound to N and are neither repointed nor revoked. Superseded
  snapshots remain viewable but are not eligible for a new public decision.
- The command does not mutate the Draft, merge Change Request comment, invoke AI, create a Job,
  change Project state, inherit Approval or create/repoint/revoke Share Links.

## Consequences

- Project-row serialization and DB uniqueness prevent two revisions from consuming one Change
  Request or allocating the same next version.
- Revision creation and target supersession roll back together.
- Applying public feedback to Scope content remains an explicit authenticated K04 edit before this
  command.

## Sources

- Owner-approved frozen 0092 contract, 2026-10-05.
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — Scope revision lifecycle; repository mirror synchronized 2026-10-05.
- [API Contract Specification](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — authenticated Scope boundary; repository mirror synchronized 2026-10-05.
- [Detailed Data Dictionary](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Scope Version baseline; repository mirror synchronized 2026-10-05.
- ADR-044, ADR-045 and ADR-078.

**Unapproved assumptions:** None
