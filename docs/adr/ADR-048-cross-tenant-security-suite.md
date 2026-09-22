# ADR-048: Cross-Tenant Security Suite and Enumeration-Safe Audit Signal

- **Status:** Accepted
- **Date:** 2026-09-13
- **Decision owners:** Product owner and Engineering
- **Related:** S1-L03, ADR-011, ADR-018, ADR-028, ADR-032, ADR-039, ADR-044, ADR-045

## Context

The canonical security and access-control documents make tenant isolation a release blocker. They
require simultaneous Tenant A/B fixtures, server-side active Membership resolution, tenant-scoped
repositories, RLS defense in depth, safe private-resource errors and negative tests for guessed
Project and child-resource identifiers. The Sprint backlog names Project, Context, Requirement,
Gap and Scope identifiers. The current public Scope API selects immutable versions by
`project_id + version_no`; its internal UUID is not a public selector.

The access-control baseline also requires a security audit signal. A lookup outside the authorized
Tenant solely to distinguish a missing resource from an existing foreign resource would weaken the
safe-not-found boundary and create an enumeration channel.

## Decision

- S1-L03 uses two concurrently present Tenants. The attacker is an authenticated active member of
  Tenant A and has no Membership in Tenant B.
- Missing, deleted and foreign private resources return the same `404 RESOURCE_NOT_FOUND` envelope.
- Missing, empty and malformed `X-Account-ID` return `400 ACCOUNT_CONTEXT_REQUIRED`; selecting a
  valid Account without active Membership returns `403 MEMBERSHIP_REQUIRED`.
- Public Scope tests use the canonical `project_id + version_no` selector. Internal Scope Draft and
  Scope Version UUIDs are exercised only through Repository/Database/RLS checks. No debug or
  security-only route is introduced.
- Repository checks use the authorized `account_id + project_id + resource selector` predicate.
  Data API roles retain no direct table grants, and RLS remains enabled on private tables.
- A safe-not-found response emits `resource.access_denied` using only request/trace data already
  available at the API boundary. Its bounded `reason_code` is `not_visible_in_tenant_scope`.
- The event may contain request/correlation context, authorized `account_id`, requested
  `project_id`, bounded `resource_type`, operation and stable error code. It must not contain a raw
  child-resource selector, actual owner Account, customer content or an existence classification.
- The audit path performs no repository, database or other secondary lookup.

## Consequences

The suite proves the external response, repository predicate and database access layers without
creating an alternate administrative lookup. Operations cannot claim whether a denied resource
exists in another Tenant from this event alone; this is intentional. A future privileged forensic
capability requires a separate approved contract and cannot be inferred from L03.

## Deferred

- Artifact, Share and Storage identifier suites remain tied to their later public implementations.
- Timing-equality thresholds and privileged cross-Tenant forensic lookup are not defined.
- No public Scope UUID route is introduced.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L03
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — tenant scope, safe not found, audit and release blockers
- [Security & Threat Model v1.0](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit) — T-TEN-01 through T-TEN-04 and T-DB-01
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-TEN-001 through TC-TEN-010
- Owner-approved 0061 refinement dated 2026-09-13
