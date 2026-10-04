# Development Record: 0089 Authenticated Scope Share Management API

- Increment ID: `0089-authenticated-scope-share-management-api`
- Date: 2026-10-04
- Owner: Platform/API Engineering
- Related domain: Scope Sharing
- [Test report](./test-report.md)

## Scope

Expose tenant-authorized Create and Revoke commands over the existing Scope Share-Link foundation.
Create binds a new link to one exact immutable Scope Version, discloses the raw capability token
once, and replays only safe metadata. Revoke is terminal and idempotent. Keep Share URL
construction, browser bootstrap, Guest Session, Approval, Change Request, Preview sharing and UI
outside this increment.

## Source Documents

- Owner-approved frozen `0089 Authenticated Scope Share Management API` contract, 2026-10-04.
- [API Contract Specification](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — authenticated Scope share baseline; synchronized 2026-10-04.
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — Share create/revoke permissions; synchronized 2026-10-04.
- [ADR-074](../../adr/ADR-074-scope-share-link-foundation.md) — hash-only Share-Link domain foundation.
- [ADR-075](../../adr/ADR-075-public-scope-share-resolution.md) — public capability-resolution boundary.
- [ADR-076](../../adr/ADR-076-authenticated-scope-share-management-api.md) — accepted one-time disclosure, idempotency and authorization decision.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8901 | Owner 0089 Create contract | Authenticated exact-version Create route, DTO, service and tenant-scoped repository lookup | TC-8901 |
| REQ-8902 | Owner 0089 one-time disclosure | Token returned only by the acquired first command; replay stores/returns only safe link identity | TC-8902, TC-8903 |
| REQ-8903 | Owner 0089 atomicity/concurrency | Shared SQLAlchemy transaction for reservation, Share Link and safe completion reference; database uniqueness is the race guard | TC-8904, TC-8905 |
| REQ-8904 | ADR-074/076 authorization | Active role checks, member creator restriction and tenant-scoped safe-not-found resolution | TC-8906 |
| REQ-8905 | Owner 0089 Revoke contract | Exactly-empty authenticated Revoke command with terminal, same-target idempotent behavior | TC-8907 |
| REQ-8906 | Owner 0089 confidentiality | Independent response allowlist and negative checks for raw token, hash and Scope content | TC-8908 |

## Assumptions and Clarifications

The owner explicitly froze the routes, exact request bodies, one-time token disclosure, safe replay,
lost-response recovery, authorization matrix, terminal revocation and deferred product surfaces.
The existing canonical 24-hour idempotency-record TTL is reused; no new retention default or token
recovery mechanism was introduced.

**Unapproved assumptions:** None

## Changes

- Added accepted ADR-076 and updated OpenAPI, architecture, data-model and module mirrors.
- Added authenticated Create and Revoke routes with mandatory `Idempotency-Key` handling.
- Extended the Sharing Application boundary with canonical request fingerprints and safe replay
  outcomes that never persist the raw token or token hash.
- Reused the generic idempotency repository inside the same Unit of Work as Share-Link persistence.
- Added tenant-scoped exact Scope Version resolution and project-operation route keys that make
  changed targets conflict.
- Added contract, Application, HTTP and PostgreSQL concurrency/rollback coverage.

## Structure Preservation

- Domain and Application remain independent from FastAPI and SQLAlchemy.
- Authentication and tenant context stay in the HTTP dependency boundary; authorization remains in
  the Sharing Application service.
- Token generation/hash persistence remains behind the existing Infrastructure ports.
- No new migration, deployable, public listing route, URL builder, guest session, UI, Approval or
  Change Request behavior was introduced.
- Existing local 0083–0088 and 0086 work was preserved without destructive Git operations.

## Senior Review

- PASS: the raw token exists only in the first acquired command response and cannot be reconstructed
  from the database or idempotency record.
- PASS: same-key/same-payload replay returns the original Share Link identity without creating a
  second token or row; changed payload or target conflicts.
- PASS: reservation, Share Link and safe replay reference share one short transaction; rollback
  leaves neither an orphan link nor an orphan reservation.
- PASS: simultaneous commands rely on the existing PostgreSQL uniqueness constraint as the final
  race guard rather than an Application-only pre-check.
- PASS: Owner/Admin/Member Create and creator-scoped Member Revoke semantics are enforced server-side
  with tenant-safe not-found outcomes.
- PASS: responses, logs and idempotency persistence exclude token hash, Scope content and tenant or
  creator internals.

## Verification

See [test-report.md](./test-report.md). Focused contract, Application, HTTP and PostgreSQL tests
passed. The complete repository test suite ran against PostgreSQL and all required lint, typecheck,
build and architecture/documentation validation gates passed.

## Remaining Risks

- Losing the first successful Create response intentionally requires revoke plus a new key/Create;
  the raw token cannot be recovered.
- Share URL construction, browser bootstrap, Guest Session and management UI remain deferred.
- Approval, Change Request, Preview sharing and authenticated Share listing require separate
  contracts.

**Final status:** PASS
