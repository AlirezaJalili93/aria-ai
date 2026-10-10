# Development Record: 0091 Public Scope Change Request

- Increment ID: `0091-public-scope-change-request`
- Date: 2026-10-05
- Owner: Platform/API Engineering
- Related domain: Scope Sharing / Change Request
- [Test report](./test-report.md)

## Scope

Add a public, capability-authorized command that records one independent immutable Change Request
for the exact Scope Version bound to a valid Share Link. Persist the version number/hash and
canonical bounded comment, move only that Scope Version from `awaiting_approval` to
`changes_requested`, and serialize the decision with public Approval so exactly one terminal
outcome can commit. Keep authenticated revision, Scope regeneration, new Scope-Version creation,
Draft mutation, Project mutation, Share-Link revocation and UI outside this increment.

## Source Documents

- Owner-approved frozen `0091 Public Scope Change Request` contract, 2026-10-05.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08-05/07 and change-request boundary; synchronized 2026-10-05.
- [API Contract Specification](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — public Scope decision baseline; synchronized 2026-10-05.
- [Detailed Data Dictionary](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Scope Version and older combined Approval baseline; synchronized 2026-10-05.
- [Test Strategy](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-APR-003/005 and E2E-05; synchronized 2026-10-05.
- [Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — Scope decision delivery sequence; synchronized 2026-10-05.
- [ADR-078](../../adr/ADR-078-public-scope-change-request.md) — accepted independent aggregate, terminal-decision and safe public API contract.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9101 | Owner 0091 independent aggregate | Immutable `scope_change_requests` model/migration with exact capability and snapshot lineage | TC-9101, TC-9105 |
| REQ-9102 | Owner 0091 terminal-decision contract | Approval and Change Request lock the same ScopeVersion and use guarded terminal transitions | TC-9102, TC-9106 |
| REQ-9103 | Owner 0091 comment contract | NFC, canonical LF, outer trim, preserved internal structure, 1–4000 characters and control rejection | TC-9103 |
| REQ-9104 | Owner 0091 HTTP/idempotency contract | Body-token public POST; first 201; exact replay 200; changed semantics 409; capability-safe errors | TC-9104, TC-9107 |
| REQ-9105 | PRD FR-08-05/07 | Change Request captures exact version/hash but does not create a replacement ScopeVersion | TC-9101, TC-9108 |
| REQ-9106 | Owner 0091 leakage contract | Allowlisted response and telemetry exclude comment, guest name, token/hash, version hash and Scope content | TC-9104, TC-9109 |
| REQ-9107 | Architecture/Tenant baseline | Restrictive composite FKs, immutable rows, RLS and no Data API grants | TC-9105, TC-9110 |

## Assumptions and Clarifications

The owner explicitly froze the separate Change Request aggregate, exact comment normalization,
one terminal decision per Scope Version, database/transaction serialization, replay semantics,
safe public failures and the absence of automatic revision behavior. The older combined
`scope_approvals.approval_type=changes_requested` shape is superseded for this implementation.

**Unapproved assumptions:** None

## Changes

- Added accepted ADR-078 and updated OpenAPI, architecture, data-model, module and migration mirrors.
- Added the Change Request Domain model, Application service/ports and PostgreSQL repository/UoW.
- Added migration `0036_scope_change_requests` with exact tenant/version/link foreign keys,
  immutable rows, one-row-per-Scope-Version uniqueness, canonical comment constraints, RLS and
  fail-closed Data API privileges.
- Added `POST /api/v1/public/scope-shares/request-changes` with exact request validation,
  capability-scoped guest idempotency, 201/200 replay semantics and no-store responses.
- Extended public Approval to return the committed Change Request winner when its race loses.
- Added Domain, Application, HTTP, contract, PostgreSQL rollback/security and real concurrency
  tests.

## Structure Preservation

- Domain and Application do not import FastAPI, SQLAlchemy or provider code.
- The public route has no JWT/Tenant-header dependency; controlled hash-only capability resolution
  remains in Infrastructure.
- `scope_approvals` continues to represent only actual Approval; Change Requests have a separate
  aggregate and audit trail.
- Both decision paths lock and guard the existing immutable ScopeVersion instead of introducing a
  second decision source of truth.
- Scope Draft, Project and Share Link are not mutated; no replacement ScopeVersion or regeneration
  command was introduced.
- Raw token, token hash, comment, guest name, version hash and Scope content are absent from public
  telemetry and the response omits comment/version hash.
- Existing local work was preserved without reset, clean, commit or push.

## Senior Review

- PASS: real PostgreSQL concurrency allows exactly one Approval or Change Request to commit.
- PASS: the race loser receives the stable error matching the committed terminal state.
- PASS: Change Request insertion and ScopeVersion transition roll back together on failure.
- PASS: exact version number/hash and capability lineage are persisted without raw token storage.
- PASS: immutable trigger, composite foreign keys, unique guards, RLS and revoked Data API access
  are active in the migrated schema.
- PASS: canonical comment handling preserves internal LF/whitespace and rejects prohibited controls.
- PASS: Project status, ShareLink revocation and ScopeVersion cardinality remain unchanged.

## Verification

See [test-report.md](./test-report.md). Focused contract/Domain/Application/API/PostgreSQL tests and
the complete PostgreSQL-backed repository suite passed. Lint, typecheck, build and architecture
validation also passed.

## Remaining Risks

- `guest_name` remains display/audit attribution, not verified Guest identity.
- A Change Request does not itself produce revised Scope content; the authenticated revision
  command remains deferred.
- Public historical resolution remains independent from decision eligibility by design.

**Final status:** PASS
