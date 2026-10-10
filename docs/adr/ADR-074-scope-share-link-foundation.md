# ADR-074 — Scope Share-Link Domain and Secure Token Foundation

- **Status:** Accepted — owner approval received 2026-10-03
- **Story:** 0087 — Scope Share-Link Domain & Secure Token Foundation
- **Extends:** ADR-045 Scope Version Snapshot; ADR-048 Cross-Tenant Security Suite

## Decision

0087 introduces a tenant-scoped `ScopeShareLink` bound to exactly one immutable
`ScopeVersion`. A link stores `account_id`, `project_id`, `scope_version_id`, a one-way token
hash, mandatory expiry, optional terminal revocation, creator identity and creation time. It never
resolves a latest Scope Version and is never repointed when a newer Version is created.

The application exposes authenticated create and revoke contracts only. Public guest resolution,
public rendering, preview sharing, approval, change requests and UI are deferred. No public HTTP
route is added in 0087; any later mutating route must add its own frozen idempotency contract before
exposure.

## Token and lifecycle contract

The issuer obtains exactly 32 bytes from a cryptographically secure random source and encodes them
as unpadded Base64URL. The persisted hash is SHA-256 over the UTF-8 bytes of that public token.
`token_hash` is a unique, non-null 32-byte value. The raw public token is returned only by the
successful create result and is never persisted, logged, emitted to Analytics, placed in an error,
or recoverable from authenticated reads.

`expires_at` is required and must be strictly later than creation time. No duration default exists.
Access eligibility is derived synchronously as `revoked_at IS NULL AND now < expires_at`; no
scheduler is a security dependency. Revocation is terminal. A second revoke is an idempotent no-op,
while clearing or changing a persisted revocation time is forbidden. Re-sharing creates a new row
and new token. Hard deletion is forbidden.

The older generic Data Dictionary `share_links` resource/status projection is superseded for this
Scope-only foundation. 0087 uses an exact `scope_version_id` and derives lifecycle from expiry and
revocation timestamps rather than persisting a second status source of truth.

## Authorization and tenant isolation

The Access Control Matrix is frozen for this increment as follows:

- active `owner`, `admin` and `member` Memberships may create a link for an exact visible Scope
  Version in their current Account and Project;
- active `owner` and `admin` may revoke any link in that Project;
- an active `member` may revoke only a link whose `created_by` is that member;
- inactive Memberships are denied, and missing, cross-tenant or member-not-visible revoke targets
  use the same outward-safe not-found application result.

Repository lookup is always scoped by the current `account_id` and `project_id`; no secondary
out-of-tenant existence probe is permitted. Composite foreign keys enforce Account → Project →
ScopeVersion consistency at the database boundary. Account, Project, ScopeVersion and Creator
references use `ON DELETE RESTRICT`.

RLS is enabled and `PUBLIC`, `anon` and `authenticated` retain no direct table privileges under the
accepted pre-M010 fail-closed architecture. Existing application-owned database access is not
redesigned by this increment.

## Persistence and observability

Database constraints enforce token-hash size/uniqueness, future expiry relative to creation,
chronological revocation, restrictive foreign keys and immutable identity fields. Tenant-leading
indexes support exact target and revocation lookups. A database trigger forbids deletion,
reactivation and mutation outside the one allowed active-to-revoked transition.

Safe operational events are `scope_share_link.created`, `scope_share_link.revoked`,
`scope_share_link.revoke_replayed` and `scope_share_link.persistence_failed`. They may contain safe
IDs, actor, operation, status and duration. Raw token, token hash, Scope snapshot/content, trace data
and customer text are forbidden.

## Explicit exclusions

Guest token resolution and constant-time public-token verification, public Scope rendering,
authenticated GET/List routes, Preview sharing, approval, change requests, UI, automatic expiry
jobs, physical deletion and any default expiry duration are outside 0087.

## Sources

- [PRD v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08; synchronized 2026-10-03.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Scope share creation baseline; synchronized 2026-10-03.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — historical Share Link baseline; synchronized 2026-10-03.
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — create and revoke permissions; synchronized 2026-10-03.
- Owner-approved 0087 contract dated 2026-10-03.
- [ADR-045 — Scope Version Snapshot](ADR-045-scope-version-snapshot.md)
- [ADR-048 — Cross-Tenant Security Suite](ADR-048-cross-tenant-security-suite.md)
