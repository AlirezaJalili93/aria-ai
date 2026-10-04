# ADR-077 — Public Scope Approval

- **Status:** Accepted — owner approval received 2026-10-04
- **Story:** 0090 — Public Scope Approval
- **Extends:** ADR-045 Scope Version Snapshot; ADR-074–076 Scope Sharing contracts

## Decision

Expose one unauthenticated bearer-capability command:

```http
POST /api/v1/public/scope-shares/approve
Idempotency-Key: <guest-command-key>
Content-Type: application/json

{
  "token": "<raw share token>",
  "guest_name": "...",
  "explicit_consent": true
}
```

The raw token remains body-only and is never persisted or emitted. The exact body is required;
`explicit_consent` must be literal Boolean `true`. `guest_name` is NFC-normalized, trimmed, 2–100
characters after normalization and cannot contain C0/C1 controls. It is display/audit attribution,
not verified identity. No email-like validation or Arabic/Persian letter conversion is performed.

## Capability, idempotency and outward behavior

Malformed, unknown, expired, revoked or inaccessible capabilities always return the existing safe
`404 RESOURCE_NOT_FOUND`. Capability resolution happens before approval-state disclosure or guest
idempotency handling.

Guest idempotency is Approval-specific and does not weaken the authenticated generic store. The
Approval row persists its capability-scoped `idempotency_key` and canonical `request_hash`; neither
contains the raw token. Same capability/key/request replays the exact original business result with
HTTP 200 and `meta.replayed=true`. Changed semantics under the same key return
`409 IDEMPOTENCY_CONFLICT`. The first success is HTTP 201. A different key after the final Approval
returns `409 SCOPE_ALREADY_APPROVED` only after the valid related capability is proven.

## Atomic final Approval

One short transaction locks the valid Share Link and exact immutable Scope Version, verifies
`awaiting_approval`, captures its exact `version_no` and `snapshot_hash`, inserts one immutable
Approval, transitions that Scope Version to `approved`, and commits the guest idempotency outcome.
`UNIQUE(scope_version_id)` is the final race guard. A rollback leaves no Approval and preserves
`awaiting_approval`. Project status is unchanged and Approval does not revoke the Share Link.

Approval persists direct tenant keys, exact Scope Version/Share Link references, `version_no`,
`version_hash`, normalized `guest_name`, literal consent, guest-idempotency state and `approved_at`.
It stores no email, IP, User-Agent or raw token. Restrictive composite foreign keys enforce exact
Account → Project → ScopeVersion → ShareLink lineage. Rows are immutable and cannot be deleted.

## Public response and confidentiality

The response allowlist contains `approval_id`, `scope_version_no`, constant status `approved`,
normalized `guest_name` and `approved_at`, plus current `request_id` and `replayed`. It excludes
`version_hash`, tenant keys, Share Link/ScopeVersion IDs and operational idempotency fields. Every
response is `Cache-Control: no-store`.

Safe events may contain Approval, Share Link, Scope Version and version-number identifiers plus
bounded outcome metadata. Raw token/hash, guest name, version hash, Scope content, IP, User-Agent
and request body are prohibited from logs, traces and Analytics.

## Explicit exclusions

Change Request, Guest Session/identity verification, public editing, automatic Share-Link
revocation, Project-status transition, Share UI and rate-limit-number selection are outside 0090.

## Sources

- Owner-approved frozen and final `0090 Public Scope Approval` contract, 2026-10-04.
- [PRD v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08 Approval baseline; synchronized 2026-10-04.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — public Approval, consent, idempotency and version-hash requirements; synchronized 2026-10-04.
- [Test Strategy v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-APR-001..004 and TC-API idempotency/security gates; synchronized 2026-10-04.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — historical Approval lineage baseline; synchronized 2026-10-04.
- [ADR-045](ADR-045-scope-version-snapshot.md), [ADR-074](ADR-074-scope-share-link-foundation.md), [ADR-075](ADR-075-public-scope-share-resolution.md), [ADR-076](ADR-076-authenticated-scope-share-management-api.md).

**Unapproved assumptions:** None
