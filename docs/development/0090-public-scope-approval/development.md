# Development Record: 0090 Public Scope Approval

- Increment ID: `0090-public-scope-approval`
- Date: 2026-10-04
- Owner: Platform/API Engineering
- Related domain: Scope Sharing / Approval
- [Test report](./test-report.md)

## Scope

Add a public, capability-authorized command that records one final approval for the exact immutable
Scope Version bound to a valid Share Link. Persist the approved Scope Version hash in the same
transaction, move that Scope Version from `awaiting_approval` to `approved`, and provide a dedicated
guest idempotency boundary without storing the raw capability token. Keep Project status, Share-Link
lifecycle, Change Requests, Guest identity verification, email collection and public editing outside
this increment.

## Source Documents

- Owner-approved frozen `0090 Public Scope Approval` final contract, 2026-10-04.
- [API Contract Specification](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Approval command, explicit consent, version-hash and response baseline; synchronized 2026-10-04.
- [Product Requirements Document](https://docs.google.com/document/d/1zObVjb3GZdhzXuBsSpBMbRhAk9hP0H2D/edit) — human Approval boundary; synchronized 2026-10-04.
- [Test Strategy](https://docs.google.com/document/d/1ctrGqR63uXs0Z5HNQqaHDZSn4dQw5FPl/edit) — exact-version and version-hash Approval acceptance; synchronized 2026-10-04.
- [Data Dictionary](https://docs.google.com/document/d/1TIZAZr_jhN57b-yXQ3SuZsICvy3ybBYg/edit) — Scope Version and Approval persistence baseline; synchronized 2026-10-04.
- [ADR-077](../../adr/ADR-077-public-scope-approval.md) — accepted public capability, guest idempotency and atomic Approval decision.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9001 | Owner 0090 endpoint contract | Public body-token Approval route with an exact request schema and mandatory `Idempotency-Key` | TC-9001, TC-9002 |
| REQ-9002 | Owner 0090 guest/consent contract | NFC-plus-trim guest-name validation, bounded length/control rejection and literal-true consent | TC-9003 |
| REQ-9003 | API Contract / TC-APR-002 | Approval captures the exact immutable Scope Version number and `version_hash` while the public DTO omits the hash | TC-9004, TC-9005 |
| REQ-9004 | Owner 0090 atomicity contract | Approval insert, Scope Version transition and guest idempotency outcome share one PostgreSQL transaction | TC-9006, TC-9007 |
| REQ-9005 | Owner 0090 idempotency contract | First success is 201, same-key replay is 200 with the same business result, and changed semantics conflict | TC-9002, TC-9008 |
| REQ-9006 | Owner 0090 capability/security contract | Invalid capabilities are outward-safe 404; raw token, version hash and customer content are excluded from logs and responses | TC-9005, TC-9009 |

## Assumptions and Clarifications

The owner explicitly froze the route, request/response semantics, guest-name normalization,
literal consent, capability-first resolution, dedicated guest idempotency, exact version-hash
capture, atomic state transition, single final Approval, unchanged Project status and independent
Share-Link lifecycle. No Guest identity verification or Change Request behavior was inferred.

**Unapproved assumptions:** None

## Changes

- Added accepted ADR-077 and updated the OpenAPI, architecture, data-model, migration and module
  mirrors.
- Added the Scope Approval Domain model, Application service/ports and controlled PostgreSQL
  repository/Unit-of-Work implementation.
- Added migration `0035_scope_approvals` with restrictive composite foreign keys, immutable Approval
  records, one-Approval-per-Scope-Version uniqueness, consent/name/hash checks, RLS and revoked public
  access.
- Added the public Approval endpoint with exact-body validation, first-response/replay HTTP status
  semantics and `Cache-Control: no-store`.
- Added focused Domain, Application, HTTP, contract and PostgreSQL concurrency/rollback tests.

## Structure Preservation

- Domain and Application remain independent from FastAPI and SQLAlchemy.
- The public route receives no authenticated tenant context; capability resolution and exact
  Scope-Version association remain behind the controlled Infrastructure repository.
- Raw capability tokens are hashed in memory and are never persisted in Approval or idempotency
  state.
- Scope Version is the existing immutable source of truth; Approval stores its exact identity,
  version number and hash without creating another Scope snapshot.
- Project status and Share-Link revocation state are not modified by Approval.
- No Change Request, Guest session, email/IP/User-Agent persistence, public editing or UI behavior
  was introduced.
- Existing local 0083–0089 and 0086 work was preserved without destructive Git operations.

## Senior Review

- PASS: the exact Scope Version hash is captured in the Approval transaction and is absent from the
  public response.
- PASS: first success returns 201; same-key/same-request replay returns 200 and preserves the original
  Approval ID, version number, guest name and timestamp.
- PASS: database uniqueness is the final guard for concurrent different-key Approval attempts.
- PASS: a forced finalization failure rolls back both Approval and Scope Version status.
- PASS: Project status and Share-Link lifecycle remain unchanged.
- PASS: invalid, malformed, expired and revoked capabilities retain outward-safe not-found behavior.
- PASS: responses and structured logs exclude raw token, token hash, version hash and Scope content.

## Verification

See [test-report.md](./test-report.md). Focused contract, Domain, Application, HTTP and PostgreSQL
tests passed. The complete repository test suite ran against PostgreSQL; lint, typecheck, build and
architecture/documentation validation gates also passed.

## Remaining Risks

- `guest_name` is attribution text, not verified identity.
- Approval does not consume or revoke the Share Link; capability lifecycle remains independent.
- Change Requests, Guest identity/session, Approval UI and public editing require separate contracts.

**Final status:** PASS
