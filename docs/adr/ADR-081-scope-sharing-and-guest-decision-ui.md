# ADR-081 — Scope Sharing and Guest Decision UI

- **Status:** Accepted
- **Date:** 2026-10-10
- **Increment:** `0094-scope-sharing-guest-decision-ui`
- **Extends:** ADR-074 through ADR-080

## Context

The secure Share-Link, public resolution, approval, change-request and revision contracts exist, and
ADR-080 provides exact-version projections plus a fragment-only browser bootstrap. The MVP still
needs the SCR-14..17 user experience without weakening the capability-token boundary, exposing
internal Scope lineage, or inventing new lifecycle behavior.

## Decision

- Add authenticated Share Settings at
  `/projects/{projectId}/scope/versions/{versionNo}/share`. It uses existing exact-version
  Create/List/Revoke/Decision APIs. Expiration remains explicit with no UI default; local input is
  converted to UTC for the API. `can_revoke` is presentation metadata only.
- Raw token and the constructed `/scope-review#token=...` URL exist only in client memory after the
  first successful Create response. Clipboard write requires an explicit gesture. Exact replay with
  `token_available=false` never reconstructs a token and instructs the user to revoke then create
  with a new Idempotency-Key.
- A superseded ScopeVersion may still be resolved through an existing historical ShareLink, but new
  ShareLink creation is rejected server-side. The UI mirrors this state; it is not the security
  boundary.
- Harden public resolution to a recursive allowlist of `{section_id, value}`. Remove `trace`,
  provenance UUID arrays, `item_id`, internal lineage/DB identifiers and `version_hash`. The
  authenticated internal Scope DTO is unchanged.
- Complete `/scope-review` as a read-only RTL presentation of all twelve public sections with the
  static title `مرور محدوده پروژه`. `approved`, `changes_requested` and `superseded` are final,
  read-only views. Only `awaiting_approval` exposes existing approval/change commands.
- Approval requires normalized guest name, literal consent and confirmation. Change Request
  requires normalized guest name and comment. A stable client-generated Idempotency-Key is reused
  across network/5xx retry. Form state and capability remain in volatile memory on retryable failure.
  The capability is cleared only after a confirmed successful terminal mutation or unmount.
- No token, guest name, comment, Scope content or Share URL is emitted to logs, metrics, traces,
  Analytics or persistent browser storage. No new Product Analytics event is added.

## Consequences

- No migration, endpoint or deployable service is introduced.
- Historical immutable snapshots remain viewable while decision eligibility stays exact-version and
  terminal-state controlled.
- Refresh after fragment removal intentionally loses the capability. This security trade-off remains
  explicit for MVP.
- Public rendering uses a dedicated allowlisted DTO rather than serializing the internal Scope model.

## Sources

- Owner-approved frozen `0094 SCR-14..17 UI` contract, 2026-10-10.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08; reviewed 2026-10-10.
- [Engineering Backlog](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — Sharing/Approval UI sequence; reviewed 2026-10-10.
- [UX Information Architecture v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — SCR-14..17; reviewed 2026-10-10.
- [Frontend UX State Management Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — Share/Guest states; reviewed 2026-10-10.
- ADR-074 through ADR-080.

**Unapproved assumptions:** None
