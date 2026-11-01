# Development Record: 0046 — Requirement Review UI

- **Status:** COMPLETE
- **Increment:** S1-I04
- **Source sync date:** 2026-09-07
- [Test report](./test-report.md)

## Scope

Implement the approved RTL-first Requirement review route over the existing I03 API: API-backed
list/filter/pagination, manual addition, explicit confirmation, edit with optimistic concurrency,
draft deactivation, truthful technical source trace and complete recovery states. Requirement
generation, restore, merge, Scope Snapshot behavior and invented Source metadata remain outside
I04.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I04
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Requirement endpoints
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — list/edit/error/conflict/unsaved states
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership and tenant isolation
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — human review and traceability
- [Aria AI Design System — Master](../../../design-system/MASTER.md)
- [ADR-032 — Requirement CRUD](../../adr/ADR-032-requirement-crud-contract.md)
- [ADR-033 — Requirement Review UI](../../adr/ADR-033-requirement-review-ui.md)
- Owner-approved I04 continuation contract dated 2026-09-07.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4601 | Backlog I04; API Contract | Tenant-authorized route and Project Overview navigation | TC-4601 |
| REQ-4602 | Backlog I04; ADR-032 | API-backed category/status filtering and opaque cursor pagination | TC-4602 |
| REQ-4603 | Backlog I04; API Contract | Retry-stable inline manual-add form with approved four input fields | TC-4603 |
| REQ-4604 | UX State; ADR-032 | Explicit confirm/edit/deactivate lifecycle controls with CAS and confirmed-edit demotion warning | TC-4604 |
| REQ-4605 | PRD; Data/API provenance contract | Truthful technical Source References, unsupported signal and no invented Source metadata | TC-4605 |
| REQ-4606 | UX State; Design System | Loading/empty/filter/partial/error/conflict/unsaved states, RTL tokens, focus and 44px targets | TC-4606 |
| REQ-4607 | Analytics baseline; owner contract | Deduplicated safe `requirement_edited` and `requirement_removed` instrumentation | TC-4607 |
| REQ-4608 | AGENTS quality gate | ADR, records, tests, full gates and Senior review | TC-4608 |

## Assumptions and Clarifications

- The API's technical `source_id`, `source_version_id` and offsets are shown exactly as available;
  Source titles, filenames, excerpts and navigation are deferred because no approved read contract
  supplies them.
- The default unfiltered API view contains active Requirements only, while explicit status filters
  can request terminal states according to ADR-032.
- Product analytics remains the existing versioned internal instrumentation; no provider or new
  integration is introduced.
- **Unapproved assumptions:** None

## Changes

- Added the `/projects/{projectId}/requirements` server route and linked it from Project Overview.
- Added a strict server-only Requirement API adapter and Server Actions for list, add, edit,
  confirm and deactivate operations.
- Added an RTL review component with API-backed filters, incremental loading, mutation feedback,
  unsaved-edit protection and explicit lifecycle controls.
- Added fail-closed public response validation for categories, states, timestamps, confidence and
  Source Reference offset pairs.
- Extended safe product analytics with Requirement edit/removal outcomes and duplicate-emission
  suppression.
- Added token-driven responsive styles and focused Web contract regression tests.

## Structure Preservation

- Preserved `Next.js route → Server Action/API adapter → I03 HTTP API`; Web does not access the
  database, Supabase internals, Queue or AI Provider.
- Tenant identity comes only from the established authenticated Account resolution; route,
  Project and Requirement IDs never establish authority.
- Backend I03 remains the lifecycle, optimistic-concurrency, idempotency and provenance authority.
- Reused canonical design tokens and Project shell. No new deployable, dependency, endpoint,
  domain field or Provider was introduced.

## Senior Review

- **Contract parity:** PASS. The route exposes only list/filter/pagination, approved manual fields,
  explicit confirmation/edit and draft deactivation. Generation, merge, restore, Source labels
  and Scope Snapshot behavior remain absent.
- **Tenant/security:** PASS. Every Server Action resolves the authenticated selected Account before
  forwarding the Bearer token and `X-Account-ID`; inaccessible Project/Requirement responses do
  not disclose cross-tenant existence. The Web layer never treats route IDs as authorization.
- **Concurrency/idempotency:** PASS. Create retries preserve their key for an identical submission,
  PATCH always forwards the current `expected_updated_at`, conflicts remain distinct, and client
  analytics suppress repeated emission of the same successful server result.
- **Data integrity:** PASS. The adapter rejects unknown enums, invalid timestamps/confidence and
  incomplete or non-increasing Source Reference offsets before rendering. Editable fields exclude
  provenance, origin, Context Version and generation metadata.
- **UX/accessibility:** PASS by deterministic contract review and production build. Labels, live
  status/error regions, visible focus for controls/details, reduced-motion behavior, logical RTL
  properties, token-only colors and minimum control heights are present. Failed list/mutation
  requests retain current content and expose recovery guidance.
- **Privacy/observability:** PASS. Product events carry versioned identifiers and role only;
  Requirement title, description, acceptance note, raw Source References, JWT and request payload
  are excluded. The 541-file secret scan passed.
- **React/Next.js review:** PASS. The route is server-authenticated, mutating code stays in Server
  Actions, no provider/database client enters the browser, action pending state uses React form
  semantics, and production compilation registers the expected dynamic route.

## Verification

- Focused Web lint and strict TypeScript: PASS.
- Focused Web contract tests: 26 passed.
- Full mandatory test command: PASS — records 6, Contract CI 122, Eval 8, Web 26, API 256 and
  Worker 57 passed. API reported 91 PostgreSQL tests skipped because this Web-only run had no
  `TEST_DATABASE_URL`; I04 changes no migration, repository or database contract.
- Full lint, strict typecheck and production build: PASS.
- Mandatory validation, secret scan and diff check: PASS.

## Remaining Risks

- Authenticated hosted-browser verification requires a deployed preview with a real test session;
  it remains separate from deterministic CI and must not be represented as completed evidence.
- Human-readable Source labels remain deferred until their canonical API/product contract exists.
