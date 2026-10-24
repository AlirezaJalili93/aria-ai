# ADR-076 — Authenticated Scope Share Management API

- **Status:** Accepted — owner approval received 2026-10-04
- **Story:** 0089 — Authenticated Scope Share Management API
- **Extends:** ADR-074 Scope Share-Link Foundation; ADR-075 Public Scope Share Resolution

## Decision

0089 exposes authenticated Create and Revoke HTTP commands over the existing Scope Share-Link
Application boundary. Create targets one exact Scope Version number in a tenant-scoped Project;
Revoke targets one exact Share Link. Both commands require an active Membership and a mandatory
`Idempotency-Key`.

Create accepts the exact body `{ "expires_at": "ISO-8601" }`. No expiry default exists. The first
successful request creates exactly one Share Link, persists only the token hash and returns the raw
token exactly once with `token_available=true` and `meta.replayed=false`.

## One-time disclosure and idempotency

The canonical Create fingerprint includes Account, actor, Project, Scope Version number and the
UTC-normalized expiry. A same-key replay with the same fingerprint creates neither a Share Link nor
a token. It returns the existing Share Link identity and safe metadata with `token=null`,
`token_available=false` and `meta.replayed=true`. A changed fingerprint is
`409 IDEMPOTENCY_CONFLICT`.

The idempotency record contains the request hash, status and `scope_share_link_id` only. It never
contains the raw token, token hash or a copy of the first response containing the token. The
canonical shared idempotency TTL remains 24 hours.

If the Share Link transaction commits but the caller loses the first response, replay deliberately
cannot recover the token. The safe recovery is to use the replayed Share Link ID, revoke that link,
then create a new link with a new Idempotency-Key. This is an intentional security trade-off.

The reservation, Share Link row and safe completion reference commit in one transaction. A rollback
leaves no valid token-backed Share Link or completed reservation. PostgreSQL uniqueness is the final
concurrency guard for simultaneous commands using the same key.

## HTTP and authorization

```http
POST /api/v1/projects/{project_id}/scope/versions/{version_no}/share
POST /api/v1/projects/{project_id}/scope-shares/{share_link_id}/revoke
```

Create permits active Owner, Admin and Member roles. Revoke permits active Owner/Admin for any
visible Project link, while Member may revoke only a link created by that subject. Missing,
cross-tenant and member-not-visible targets use the same safe `404 RESOURCE_NOT_FOUND`; no secondary
out-of-tenant probe is allowed.

Revoke requires an exactly empty body and returns `204`. Same-key/same-target replay returns `204`
without another transition. Reusing the key for another target is `409 IDEMPOTENCY_CONFLICT`.
Revocation remains terminal.

## Confidentiality and exclusions

Responses exclude token hash, Account ID, creator internals and Scope snapshot content. Logs,
traces, Analytics, errors and idempotency storage exclude the raw token and token hash.

Share URL construction, browser bootstrap, public UI, Guest Session, Approval, Change Request,
Preview sharing and authenticated Share listing remain deferred.

## Sources

- Owner-approved frozen 0089 contract, 2026-10-04.
- [ADR-074 — Scope Share-Link Foundation](ADR-074-scope-share-link-foundation.md)
- [ADR-075 — Public Scope Share Resolution](ADR-075-public-scope-share-resolution.md)
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — authenticated Scope share creation baseline; synchronized 2026-10-04.
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — Share create/revoke permissions; synchronized 2026-10-04.

**Unapproved assumptions:** None
