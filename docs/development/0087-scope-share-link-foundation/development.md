# Development Record: 0087 Scope Share-Link Foundation

- Increment ID: `0087-scope-share-link-foundation`
- Date: 2026-10-03
- Owner: Platform/API Engineering
- Related domain: Scope Sharing
- [Test report](./test-report.md)

## Scope

Add the secure persistence and authenticated application boundary for creating and terminally
revoking a Share Link bound to one exact immutable Scope Version. Persist only a one-way token
hash. Keep guest resolution, public rendering, approval, change requests, UI and HTTP exposure out
of this increment.

## Source Documents

- Owner-approved frozen `0087 — Scope Share-Link Domain & Secure Token Foundation` contract,
  2026-10-03.
- [PRD v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08; reread 2026-10-03.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Scope share baseline; reread 2026-10-03.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — historical Share Link baseline; reread 2026-10-03.
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — create/revoke authority; reread 2026-10-03.
- [ADR-045](../../adr/ADR-045-scope-version-snapshot.md),
  [ADR-048](../../adr/ADR-048-cross-tenant-security-suite.md) and
  [ADR-074](../../adr/ADR-074-scope-share-link-foundation.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8701 | Owner 0087 Token contract | 32-byte CSPRNG, unpadded Base64URL and SHA-256 token issuer | TC-8701 |
| REQ-8702 | Owner 0087 hash-only storage | `scope_share_links.token_hash` only; no raw/public token column or logging field | TC-8701, TC-8707 |
| REQ-8703 | Owner 0087 expiry/revocation | Required future expiry, synchronous access predicate and terminal idempotent revocation | TC-8702, TC-8703 |
| REQ-8704 | Owner 0087 ScopeVersion binding | Exact composite Account/Project/ScopeVersion FK; no latest resolution | TC-8704 |
| REQ-8705 | Access Matrix + Owner refinement | Active members create; creator or Owner/Admin revoke; safe not-found otherwise | TC-8705 |
| REQ-8706 | Owner 0087 Tenant/RLS | Tenant-scoped repository lookup, RESTRICT FKs, RLS and no Data API grants | TC-8704, TC-8706 |
| REQ-8707 | Owner 0087 observability | Safe bounded events without token/hash/snapshot/customer content | TC-8707 |
| REQ-8708 | Owner 0087 API boundary | Application create/revoke only; no guest/public route or UI | TC-8708 |

## Assumptions and Clarifications

The owner explicitly froze token construction, exact immutable ScopeVersion binding, mandatory
caller-supplied expiry, terminal revocation, no hard delete and the deferred public/UI boundary.
ADR-074 freezes the existing Access Control Matrix: every active project member may create; the
creator or an Owner/Admin may revoke. The existing pre-M010 fail-closed RLS/grant architecture is
preserved rather than redesigned.

**Unapproved assumptions:** None

## Changes

- Added ADR-074 and updated the developer data-model mirror.
- Added the isolated `sharing` Domain/Application/Infrastructure module.
- Added a secure token issuer and create/revoke application service.
- Added Migration 0034 with composite tenant consistency, RESTRICT references, indexes, RLS,
  hash/chronology checks and an immutability/terminal-revocation trigger.
- Added unit, static-contract, PostgreSQL, RLS, cross-tenant and leakage-negative coverage.

## Structure Preservation

- Domain and Application import no SQLAlchemy, FastAPI or Provider-specific code.
- Persistence, CSPRNG/hash implementation and transaction mechanics remain Infrastructure concerns.
- Scope Versions remain immutable and are referenced exactly; no latest-version lookup was added.
- No public endpoint, guest resolver, deployable service, Scheduler, UI or automatic expiry worker
  was introduced.
- Existing 0086 local work was preserved without restoration or unrelated refactoring.

## Senior Review

- PASS: raw token exists only in the successful create return value and cannot be reconstructed.
- PASS: database constraints independently enforce token hash size/uniqueness and tenant lineage.
- PASS: create/revoke authorization is Backend-owned and cross-tenant/member-hidden targets do not
  trigger an out-of-tenant probe.
- PASS: revocation is terminal in Domain and PostgreSQL; double revoke is an application no-op.
- PASS: direct Data API roles have no grants and RLS remains enabled.
- PASS: destructive parent cascades and Share Link hard deletion are absent.
- PASS: public consumption and unrelated sharing workflow behavior remain deferred.

## Verification

See [test-report.md](./test-report.md). Focused contract/unit/PostgreSQL gates and the complete API
suite passed against an isolated PostgreSQL 16 database. Repository-wide required gates passed in
the final run.

## Remaining Risks

- Public guest token resolution and public rendering require a separate contract and security gate.
- HTTP create/revoke exposure still requires a frozen request/idempotency/error contract.
- Approval, change requests, UI and any expiry cleanup remain deferred.

**Final status:** PASS
