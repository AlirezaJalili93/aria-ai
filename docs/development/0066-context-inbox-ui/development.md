# Development Record: 0066 — Context Inbox UI

- **Status:** Completed
- **Increment:** S1-D04 Context Inbox UI
- **Source sync date:** 2026-09-19
- [Test report](./test-report.md)

## Scope

Implement the approved RTL Context Inbox for pasted text and private TXT upload, Source processing
status, explicit recoverable retry, permission-aware logical archive, cursor pagination and bounded
polling. Preserve the existing Structured Context review route and exclude URL/Internal Note input,
synthetic progress, automatic retry and Storage internals.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D04; synchronized 2026-09-19.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Context Source and Job contracts; synchronized 2026-09-19.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership and server-side authorization; synchronized 2026-09-19.
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — input, processing, failure and recovery states; synchronized 2026-09-19.
- [ADR-053](../../adr/ADR-053-context-inbox-ui.md) — owner-approved frozen D04 decisions.
- [`design-system/MASTER.md`](../../../design-system/MASTER.md), `design-system.md`, and `ui-ux-pro-max.md` — approved RTL, token, accessibility and interaction guidance; reviewed 2026-09-19.

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6601 | S1-D04; ADR-053 | Dedicated `/context/sources` Inbox and internal Sources/Structured Context navigation | TC-6601 |
| REQ-6602 | S1-D04; UX states | Pasted-text and fail-closed TXT upload forms with retry-stable idempotency | TC-6602 |
| REQ-6603 | API Contract; ADR-053 | Safe Source projection, latest Version/Job state and Load More pagination | TC-6603 |
| REQ-6604 | ADR-053 | Five-second active-Job polling, hidden-document pause, terminal stop and overlap guard | TC-6604 |
| REQ-6605 | Access Control; ADR-053 | Backend-computed `can_archive`; independently authorized confirmed archive | TC-6605 |
| REQ-6606 | S1-D04; ADR-053 | Retry action only for backend-classified recoverable failures | TC-6606 |
| REQ-6607 | UX/design system | RTL, semantic controls, text-plus-SVG status, 44px targets and no fake progress | TC-6607 |
| REQ-6608 | Security baseline | No creator, content, Storage reference/object URL or secret in public types or UI | TC-6608 |

## Assumptions and Clarifications

- The Frontend upload flag controls exposure only and defaults false; the Backend remains authoritative.
- `can_archive` and `retryable` are independent, bounded capabilities and imply no other permission.
- Archive remains logical and preserves versions, provenance and Storage objects.
- Automatic processing scheduling and automatic retry remain outside D04.

**Unapproved assumptions:** None

## Changes

- Added accepted ADR-053 and the public `NEXT_PUBLIC_TXT_UPLOAD_ENABLED=false` baseline.
- Added backend-owned `can_archive` calculation in the Context Application service and included only
  the Boolean capability in Source list/detail projections; creator identity stays internal.
- Added strict Frontend response parsing that fails closed and models no raw content, creator or
  Storage implementation fields.
- Added tenant-authorized Server Actions for text creation, TXT upload, refresh, pagination,
  archive and explicit retry. Text idempotency fingerprints are SHA-256 digests, not customer text.
- Added the Context Inbox route, two-source navigation, safe Persian status/error copy, empty state,
  cursor Load More, archive confirmation and retry visibility controlled by the backend response.
- Added visibility-aware, non-overlapping five-second polling only while a loaded Job is active,
  plus an independent manual refresh.
- Added token-only responsive styles using the existing design system and one SVG status family.
- Added Web contract tests and Backend Application/API tests for permission projection and leakage.

## Structure Preservation

- PASS: `/projects/{projectId}/context` remains the Structured Context surface; the Inbox has its
  own `/context/sources` route.
- PASS: backend authorization is calculated in Application and re-enforced by the mutation endpoint;
  the UI does not derive permission from role or creator metadata.
- PASS: the Frontend adapter uses existing API boundaries and adds no provider SDK, service or
  persistence model.
- PASS: raw colors were not added; primitive-to-semantic-to-component token structure is preserved.
- PASS: URL/Internal Note, automatic retry, scheduler behavior, fake progress and Storage GC remain
  outside the increment.

## Senior Review

- PASS: response parsing rejects malformed UUID, datetime, status, version, job and capability data.
- PASS: polling is conditional, pauses while hidden, cannot overlap, and ends once no loaded active
  Job remains.
- PASS: Source cards communicate status with visible Persian text in addition to SVG; every action
  is a semantic button with the existing minimum target and focus treatment.
- PASS: archive visibility uses only `can_archive`; retry visibility uses only `retryable`; the
  frontend flag is used only for upload exposure.
- PASS: error rendering uses bounded safe mappings and never shows provider responses or raw errors.
- FIXED DURING REVIEW: the initial customer-text idempotency fingerprint was replaced with a SHA-256
  digest so Server Action state does not mirror raw customer text.
- FIXED DURING REVIEW: Server-generated idempotency keys replaced render-time browser UUID creation,
  avoiding hydration instability while preserving retry-stable commands.
- FIXED DURING REVIEW: prop-to-state synchronization effects were removed; request-id keyed remounts
  now make completed server refreshes deterministic without cascading render effects.

## Verification

Contract-first Web tests were red before the route and components existed, then passed after
implementation. Focused Backend and Frontend tests, lint and type checks pass. Full repository
verification is recorded in the linked test report.

## Remaining Risks

- TXT upload remains hidden unless the explicit public UI flag is enabled; Backend enablement and
  hosted Storage security gates remain independently authoritative.
- Polling is the approved Sprint 1 mechanism; SSE and continuous worker scheduling remain deferred.
- Physical Storage retention/GC and URL/Internal Note ingestion require separate approved contracts.
- Model/provider-backed parsing quality remains outside this deterministic UI increment.

**Final status:** PASS
