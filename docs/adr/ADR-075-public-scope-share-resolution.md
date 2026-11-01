# ADR-075 — Public Scope Share Resolution

- **Status:** Accepted — owner approval received 2026-10-04
- **Story:** 0088 — Public Scope Share Resolution
- **Extends:** ADR-074 Scope Share-Link Foundation

## Decision

Expose one unauthenticated capability endpoint:

```http
POST /api/v1/public/scope-shares/resolve
Content-Type: application/json

{"token":"<raw share token>"}
```

The route accepts neither Bearer authentication nor `X-Account-ID`; possession of the token is the
only capability. The token is allowed only in the JSON body. Path and query token transport are
prohibited.

Request validation first requires the exact object shape with one non-null string `token`. Missing,
null and additional properties are `422 VALIDATION_FAILED`. A syntactically valid body containing a
malformed, noncanonical, unknown, expired or revoked token, or a missing/inaccessible bound resource,
always produces the same `404 RESOURCE_NOT_FOUND` envelope.

## Resolution and response

The application validates canonical unpadded Base64URL representing exactly 32 bytes, computes
SHA-256 over the token's UTF-8 representation, then performs one controlled hash lookup. The query
checks revocation and expiry against server time and joins the exact immutable ScopeVersion through
the persisted Account/Project/Version identity. It never resolves latest state and never performs a
secondary tenant/existence probe.

The independent public DTO allowlists only:

```yaml
data:
  version_no: integer
  snapshot_data: scope_content_schema_v1
meta:
  request_id: uuid
```

It excludes raw token, token hash, Account/Project IDs, Share Link/ScopeVersion IDs, creator,
lifecycle status, snapshot hash and other operational metadata. Every response for this route,
including 404 and 422, carries `Cache-Control: no-store`.

## Concurrency and database authority

Resolve acquires a transaction-scoped shared row lock on the Share Link. Revoke uses the existing
exclusive row lock. This yields one ordered outcome: a resolve already holding the shared lock may
complete before revocation; after revocation commits, subsequent resolution cannot succeed. No
Scheduler or cache is part of the security boundary.

`PUBLIC`, `anon` and `authenticated` receive no direct SELECT privilege or RLS policy on Share Links
or Scope Versions. Resolution runs through the controlled Application/Repository path using the
existing server database authority. The unique token-hash index is the lookup path.

## Confidentiality and observability

Request-body logging is prohibited. Raw token and its hash are prohibited from logs, traces,
Analytics, errors and response data. Safe events are `scope_share.resolve_succeeded`,
`scope_share.resolve_not_found` and `scope_share.resolve_failed`; they contain only request
correlation metadata and, after successful lookup, safe Share Link/Scope Version identifiers.

## Explicit exclusions

Approval, change requests, Preview sharing, public editing, guest identity/session, Share UI,
authenticated Share management HTTP routes and response caching are outside 0088.

## Sources

- Owner-approved frozen `0088 Public Scope Share Resolution` contract, 2026-10-04.
- [PRD v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08 read-only exact ScopeVersion sharing; synchronized 2026-10-03.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — public envelope and safe error conventions; synchronized 2026-10-03.
- [ADR-074 — Scope Share-Link Foundation](ADR-074-scope-share-link-foundation.md)
