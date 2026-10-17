# ADR-080 — Scope Review Projections and Secure Browser Bootstrap

- **Status:** Accepted
- **Date:** 2026-10-05
- **Increment:** `0093-scope-review-projections-browser-bootstrap`
- **Extends:** ADR-074, ADR-075, ADR-077, ADR-078, ADR-079

## Context

Authenticated Share management and the public capability commands exist, but the Share Settings UI
has no safe read model for links or final decisions. The public resolver also needs the state of its
exact immutable Scope Version. A browser entry point must receive the one-time bearer capability
without placing it in an HTTP path/query or persistent browser storage before the full SCR-14..17 UI
is implemented.

## Decision

- Add authenticated `GET /api/v1/projects/{project_id}/scope/versions/{version_no}/shares`.
  Owner/Admin receive all links for the exact Version; Member receives only links created by that
  actor. The allowlist is `id, scope_version_no, status, expires_at, created_at, can_revoke`.
  `can_revoke` is server-computed presentation metadata and does not replace Revoke authorization.
- Add authenticated `GET /api/v1/projects/{project_id}/scope/versions/{version_no}/decision` with a
  discriminated `none | approval | change_request` projection. Approval exposes its safe public
  attribution fields; Change Request additionally exposes `comment` to the authorized tenant
  member. Token/hash/version-hash fields remain absent and comment is prohibited from telemetry.
- Add `decision_status = awaiting_approval | approved | changes_requested | superseded` to public
  resolve. It is always read from the exact ScopeVersion bound to the ShareLink, never a latest
  Project Version.
- Use `/scope-review#token=<raw-token>` for the MVP browser entry. Client bootstrap reads and
  validates the fragment, immediately calls `history.replaceState` to `/scope-review`, retains the
  capability only in volatile browser memory, and only then may call the body-token resolve API or
  initialize telemetry.
- Raw capability persistence in localStorage, sessionStorage, IndexedDB, cookies, query/path,
  diagnostics, telemetry or error context is prohibited. Refresh intentionally loses the token and
  requires reopening the original link.
- Public review uses the static title `مرور محدوده پروژه`. It performs no live Project/Client-title
  lookup. Full Share Settings and Guest Review/Approve/Change UI remains 0094.

## Consequences

- No migration or public Data API grant is introduced; projections use existing tenant-scoped
  Application/Repository boundaries and immutable decision tables.
- Historical ShareLinks keep resolving their exact snapshot and exact historical decision status.
- URL fragments are not transmitted in HTTP request targets, but remain accessible to page scripts;
  therefore fragment clearing precedes all third-party scripts and telemetry by contract.

## Sources

- Owner-approved frozen 0093 contract, 2026-10-05.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08 Sharing/Guest Review baseline; reviewed 2026-10-05.
- [Engineering Backlog v1.0](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — EP-E3/E4 projections and guest review; reviewed 2026-10-05.
- [UX Information Architecture v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — SCR-14..17; reviewed 2026-10-05.
- [Frontend UX State Management Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — SH/GA states; reviewed 2026-10-05.
- ADR-074 through ADR-079.

**Unapproved assumptions:** None
