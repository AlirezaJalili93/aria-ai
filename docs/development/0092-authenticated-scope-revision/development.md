# Development Record: 0092 Authenticated Scope Revision

- Increment ID: `0092-authenticated-scope-revision`
- Date: 2026-10-05
- Owner: Platform/API Engineering
- Related domain: Scope / Revision
- [Test report](./test-report.md)

## Scope

Add an authenticated, tenant-scoped and idempotent command that consumes one exact immutable Change
Request after an explicit K04 Draft edit, creates one revised immutable Scope Version with exact
parent lineage, and supersedes the target Version in the same transaction. Prevent generic K05
creation from bypassing required lineage. Preserve historical Share-Link binding and exclude AI,
automatic regeneration, Draft mutation, Project mutation and Share-Link lifecycle changes.

## Source Documents

- Owner-approved frozen `0092 Authenticated Scope Revision Command` contract, 2026-10-05.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — revision lifecycle baseline; repository mirror synchronized 2026-10-05.
- [API Contract Specification](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — authenticated Scope API baseline; repository mirror synchronized 2026-10-05.
- [Detailed Data Dictionary](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Scope Version baseline; repository mirror synchronized 2026-10-05.
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active tenant Membership baseline; repository mirror synchronized 2026-10-05.
- [ADR-079](../../adr/ADR-079-authenticated-scope-revision.md) — accepted revision command, lineage and atomicity decision.

The Drive connector was unavailable during this increment. No new Drive-derived behavior was
claimed; the explicit owner-approved contract and already-synchronized repository mirrors were
used.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9201 | Owner 0092 flow | Authenticated Revision command snapshots the current edited Draft into N+1 and supersedes N | TC-9201, TC-9205 |
| REQ-9202 | Owner 0092 lineage | Paired parent/ChangeRequest composite FKs, immutable trigger and single-use unique constraint | TC-9202, TC-9206 |
| REQ-9203 | Owner 0092 atomicity/concurrency | Project/latest/target/ChangeRequest/Draft locks and one transaction | TC-9203, TC-9207 |
| REQ-9204 | Owner 0092 errors | Stable stale, CAS, unchanged, readiness and safe-not-found semantics | TC-9204 |
| REQ-9205 | Owner 0092 idempotency | First 201, exact replay 200 with same N+1, changed semantics conflict | TC-9201, TC-9204 |
| REQ-9206 | Owner 0092 K05 guard | Generic freeze returns `SCOPE_REVISION_REQUIRED` for latest changes_requested Version | TC-9205 |
| REQ-9207 | Owner 0092 guardrails | No comment merge, AI/Job, Draft/Project/ShareLink mutation or historical repoint | TC-9201, TC-9208 |

## Assumptions and Clarifications

The owner explicitly froze the route/body, active Membership authority, lock/revalidation order,
maximum-version definition, exact error precedence, paired lineage, Change Request single-use,
atomic supersession, historical Share-Link behavior and excluded side effects.

**Unapproved assumptions:** None

## Changes

- Added accepted ADR-079, OpenAPI operation and architecture/data-model/module mirrors.
- Added Application ports/service and PostgreSQL Repository/UoW for revision creation.
- Added migration `0037_scope_revision_lineage` with paired nullable lineage, tenant-safe composite
  FKs, single-use uniqueness, FK index and trigger-protected immutability.
- Added dynamic 201/200 replay API behavior and stable error handlers.
- Added the generic K05 `SCOPE_REVISION_REQUIRED` bypass guard.
- Added contract, Domain/Application/API and real PostgreSQL race/rollback/security tests.

## Structure Preservation

- Domain/Application remain free of FastAPI, SQLAlchemy and provider imports.
- No new deployable service, Queue task, AI call, Job or automatic orchestration was added.
- Public Change Request comment remains immutable feedback only and is not merged into the Draft.
- Existing Share Links retain exact historical ScopeVersion binding.
- Idempotency stores only the resulting ScopeVersion reference, never snapshot content.
- Telemetry excludes Draft/snapshot/comment and raw customer content.

## Senior Review

- PASS: exact replay is evaluated before post-success stale state.
- PASS: maximum `version_no`, target, Change Request and Draft are revalidated under one Project-
  serialized transaction.
- PASS: concurrent different keys consume one Change Request exactly once.
- PASS: insertion failure leaves N in `changes_requested` and creates no N+1.
- PASS: lineage and snapshot payload are immutable at the database layer.
- PASS: historical ShareLink remains bound to N after N is superseded.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- Applying feedback remains a human K04 edit; semantic equivalence to the public comment is not
  automatically checked.
- A new Share Link for N+1 remains an explicit later command.

**Final status:** PASS
