# Development Record: 0088 Public Scope Share Resolution

- Increment ID: `0088-public-scope-share-resolution`
- Date: 2026-10-04
- Owner: Platform/API Engineering
- Related domain: Scope Sharing
- [Test report](./test-report.md)

## Scope

Expose one unauthenticated, body-only capability endpoint that resolves an active Share Link to its
exact immutable Scope Version. Apply synchronous expiry/revocation enforcement, an independent
public response allowlist and `no-store` to every route outcome. Keep approval, change requests,
Preview sharing, public editing, guest identity/session, Share UI and authenticated management HTTP
routes outside this increment.

## Source Documents

- Owner-approved frozen `0088 Public Scope Share Resolution` contract, 2026-10-04.
- [ADR-045](../../adr/ADR-045-scope-version-snapshot.md) — immutable Scope Version authority.
- [ADR-048](../../adr/ADR-048-cross-tenant-security-suite.md) — safe-not-found and no existence
  oracle.
- [ADR-074](../../adr/ADR-074-scope-share-link-foundation.md) — hash-only Share Link foundation.
- [ADR-075](../../adr/ADR-075-public-scope-share-resolution.md) — accepted 0088 transport,
  resolution, response, concurrency and confidentiality decision.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8801 | Owner 0088 endpoint contract | Public `POST /api/v1/public/scope-shares/resolve`; exact body model; no auth dependency | TC-8801, TC-8802 |
| REQ-8802 | Owner 0088 capability contract | Canonical 32-byte unpadded Base64URL validation followed by SHA-256 hash lookup | TC-8803 |
| REQ-8803 | Owner 0088 safe-not-found | Malformed/unknown/expired/revoked/inaccessible capabilities map to the same 404 | TC-8802, TC-8804 |
| REQ-8804 | Owner 0088 immutable snapshot | Composite exact-version join; independent DTO with only `version_no` and `snapshot_data` | TC-8801, TC-8805 |
| REQ-8805 | Owner 0088 cache boundary | Exact-route ASGI middleware applies `Cache-Control: no-store` to success and errors | TC-8801, TC-8802 |
| REQ-8806 | Owner 0088 concurrency | Resolve shared row lock serializes with exclusive terminal revocation | TC-8806 |
| REQ-8807 | Owner 0088 DB authority | No `PUBLIC`/`anon`/`authenticated` grant or RLS policy; controlled repository only | TC-8807 |
| REQ-8808 | Owner 0088 confidentiality | No raw token/hash/snapshot in logs, errors, response metadata, path or query | TC-8808 |

## Assumptions and Clarifications

The owner explicitly froze POST/body-only capability transport, uniform outward-safe 404 behavior,
exact immutable Scope Version binding, no-store responses, no direct public database grants and the
deferred guest/UI/approval boundary. ADR-075 records the minimal public DTO without exposing tenant,
creator, Share Link, Scope Version or lifecycle internals.

**Unapproved assumptions:** None

## Changes

- Added accepted ADR-075 and updated the architecture mirror.
- Added the provider-neutral public resolver with canonical token validation and safe events.
- Added an exact hash/expiry/revocation/composite-lineage repository query using a shared row lock.
- Added a public FastAPI route with strict request and response DTOs.
- Added exact-route `Cache-Control: no-store` middleware for success and error responses.
- Added OpenAPI, static contract, unit, HTTP, logging-negative and PostgreSQL concurrency coverage.

## Structure Preservation

- Domain and Application remain independent from FastAPI and SQLAlchemy.
- Token hashing and SQL locking remain Infrastructure concerns behind existing ports.
- No latest-version resolution, public database role grant, new deployable, cache, Scheduler or
  background expiry process was introduced.
- Existing 0086/0087 local work was preserved without unrelated restoration or refactoring.

## Senior Review

- PASS: request-shape failure is distinct from invalid capability, while every invalid capability
  state remains outwardly identical.
- PASS: the response is an independent allowlist and cannot expose token, tenant or operational
  identity.
- PASS: shared/exclusive row locks give revoke-vs-resolve an ordered database outcome.
- PASS: exact Account/Project/ScopeVersion association is enforced without latest lookup or a
  secondary existence probe.
- PASS: no-store applies to 200, 404, 422 and framework-level outcomes on the exact route.
- PASS: request telemetry and application events omit token, hash and Scope content.

## Verification

See [test-report.md](./test-report.md). Focused contract, unit, HTTP and PostgreSQL tests passed.
Repository-wide required gates passed in the final run.

## Remaining Risks

- Public presentation UI remains deferred.
- Approval, change requests, guest sessions and Preview sharing require separate contracts.
- Authenticated create/revoke HTTP exposure remains outside 0088.

**Final status:** PASS
