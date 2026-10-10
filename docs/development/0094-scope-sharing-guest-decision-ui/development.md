# Development Record: 0094 Scope Sharing and Guest Decision UI

- Increment ID: `0094-scope-sharing-guest-decision-ui`
- Date: 2026-10-10
- Owner: Platform/API/Web Engineering
- Related domain: Scope Sharing / Guest Review and Decision
- [Test report](./test-report.md)

## Scope

Complete SCR-14..17 using existing 0087–0093 APIs: authenticated exact-version Share Settings,
public twelve-section review, terminal Approval/Change Request actions, and a hardened public DTO
that removes internal lineage. Preserve fragment bootstrap, one-time disclosure, exact immutable
version binding and server-owned authorization.

## Source Documents

- Owner-approved frozen `0094 SCR-14..17 UI` contract, 2026-10-10.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08; synchronized 2026-10-10.
- [Engineering Backlog](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — Sharing/Approval UI sequence; synchronized 2026-10-10.
- [UX Information Architecture v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — SCR-14..17; synchronized 2026-10-10.
- [Frontend UX State Management Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — Share/Guest states; synchronized 2026-10-10.
- [ADR-081](../../adr/ADR-081-scope-sharing-and-guest-decision-ui.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9401 | Owner 0094 public DTO hardening | Recursive public projection removes trace, provenance IDs, item IDs and hashes | TC-9401, TC-9408 |
| REQ-9402 | Owner 0094 superseded guard | Transaction-scoped exact-version lock rejects new Share creation for superseded Version | TC-9402, TC-9409 |
| REQ-9403 | SCR-14 | Authenticated Share Settings create/list/revoke/decision UI with explicit expiry | TC-9403, TC-9407 |
| REQ-9404 | SCR-14 security | One-time token/URL stays memory-only; clipboard is explicit; replay cannot reconstruct token | TC-9404, TC-9408 |
| REQ-9405 | SCR-15 | RTL read-only rendering of all twelve allowlisted Scope sections and final states | TC-9405, TC-9407 |
| REQ-9406 | SCR-16 | Approval requires name, literal consent, confirmation and stable retry idempotency | TC-9406, TC-9408 |
| REQ-9407 | SCR-17 | Change Request preserves unsent name/comment and token on retryable failure | TC-9406, TC-9408 |
| REQ-9408 | Owner accessibility/security guardrails | Labels, focus, 44px controls, responsive layout and zero sensitive telemetry/storage | TC-9407, TC-9408 |

## Assumptions and Clarifications

The owner froze the public allowlist, superseded-version behavior, exact routes, explicit expiry,
one-time replay semantics, Guest state machine, mutation retry behavior, accessibility baseline and
the prohibition on new endpoints, telemetry and persistent capability storage.

**Unapproved assumptions:** None

## Changes

- Added ADR-081 and tightened the OpenAPI public Scope projection.
- Added server-side exact-Version lock/status validation before Share creation.
- Added strict Web parsers for public and authenticated projections.
- Added authenticated Share Settings and public review/approval/change-request UI.
- Added contract, Web, API and isolated PostgreSQL tests.

## Structure Preservation

- Domain remains free of FastAPI, SQLAlchemy, Next.js and browser imports.
- No new endpoint, migration, deployable service, DB role or public data grant was added.
- Existing 0087–0093 Application/API boundaries are reused; authorization remains server-owned.
- Internal authenticated Scope content remains unchanged; only public projection is reduced.
- Capability, guest attribution, comment and Scope content are absent from telemetry and persistent
  browser storage.

## Senior Review

- PASS: existing historical links still resolve superseded snapshots while new link creation is
  rejected under the same Project row lock used by revision finalization.
- PASS: recursive public DTO projection and strict client parsing fail closed on internal lineage.
- PASS: network/5xx failure retains volatile token, input and Idempotency-Key; only successful final
  decision clears the capability.
- PASS: Create replay cannot recover a raw token and the UI describes the revoke/new-key recovery.
- PASS: controls are semantic, labeled, keyboard reachable and use existing design tokens.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- Real-browser visual and assistive-technology checks remain part of release acceptance; source and
  build gates cover the contract but do not replace human UX validation.
- The MVP intentionally loses the capability on refresh after fragment removal.

**Final status:** PASS
