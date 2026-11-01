# Development Record: 0045 — Requirement CRUD and Human Review

- **Status:** COMPLETE
- **Increment:** S1-I03
- **Source sync date:** 2026-09-07
- [Test report](./test-report.md)

## Scope

Implement the approved tenant-scoped Requirement list, manual creation, edit, confirmation and
draft deactivation contract. The increment includes optimistic concurrency, idempotent creation,
safe pagination, `acceptance_note`, structured events and PostgreSQL migration coverage. The
Requirement UI, Scope Snapshot behavior, restore, merge, regeneration and durable audit-event
persistence remain outside I03.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I03
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Requirement endpoints and common API rules
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Requirement fields and lifecycle
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership and tenant isolation
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — edit and conflict states
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — human review and traceability
- [ADR-030 — Requirement Domain](../../adr/ADR-030-requirement-domain-contract.md)
- [ADR-031 — Requirement Generation](../../adr/ADR-031-requirement-generation-contract.md)
- [ADR-032 — Requirement CRUD](../../adr/ADR-032-requirement-crud-contract.md)
- Owner-approved I03 contract dated 2026-09-07.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4501 | I03 owner contract; API Contract | Tenant-scoped list with category/status filters, opaque descending cursor and hidden terminal states by default | TC-4501, TC-4508 |
| REQ-4502 | I03 owner contract; ADR-030 | Manual create binds current Context Version and server-owned draft/user/provenance fields | TC-4502, TC-4508 |
| REQ-4503 | Architecture rules; I03 owner contract | Mandatory 24-hour idempotency reservation; exact replay and conflict semantics | TC-4503, TC-4508 |
| REQ-4504 | I03 owner contract; UX states | PATCH CAS on `updated_at`, explicit nullable acceptance note and confirmed-edit demotion | TC-4504, TC-4508 |
| REQ-4505 | I03 owner contract; Data Dictionary | Draft-only soft deactivation; no hard delete; terminal states immutable | TC-4505, TC-4508 |
| REQ-4506 | Access Control Matrix | Active Membership access, tenant predicates and safe 404 for missing/cross-tenant resources | TC-4506, TC-4508 |
| REQ-4507 | Logging guardrail | Safe lifecycle/security/repository events without Requirement or provenance content | TC-4507 |
| REQ-4508 | AGENTS quality gate | Migration, ADR/mirror sync, development record, tests and Senior review | TC-4509 |

## Assumptions and Clarifications

- `acceptance_note` is nullable text with no invented normalization or length limit; explicit JSON
  `null` clears it.
- Manual creation is rejected when `projects.current_context_version < 1`; no Context-free manual
  Requirement path is introduced.
- DELETE implements only the approved draft-to-removed transition. Scope Snapshot detection and
  confirmed-to-superseded behavior remain deferred because their canonical persistence contract
  does not yet exist.
- Replay returns the same current Requirement resource referenced by the generic idempotency
  record; it does not introduce a second immutable result store.
- Current Supabase guidance was rechecked on 2026-09-07. Existing RLS plus explicit grants remain
  unchanged; the API continues to use direct SQLAlchemy access and does not expose these tables
  through the Supabase Data API.
- **Unapproved assumptions:** None

## Changes

- Added a framework-neutral Requirement CRUD Application service and ports over a transaction
  boundary shared with the existing generic idempotency repository.
- Added tenant-scoped SQLAlchemy list/read/lock/update operations, keyset ordering and safe default
  lifecycle filtering.
- Added GET, POST, PATCH and DELETE FastAPI routes and synchronized OpenAPI request, response and
  error contracts.
- Added nullable `acceptance_note` and the tenant-first Requirement collection index in migration
  `0013_requirement_crud`.
- Added stable `CONTEXT_VERSION_REQUIRED` and `INVALID_REQUIREMENT_STATE` error mappings.
- Added Application, API, PostgreSQL and repository contract tests plus synchronized ADR,
  architecture, data-model and migration mirrors.

## Structure Preservation

- Preserved `FastAPI Router → Application Service → Ports ← SQLAlchemy Infrastructure`; Domain and
  Application do not import FastAPI, SQLAlchemy, Supabase SDKs or provider code.
- Reused the established Tenant Context dependency, generic idempotency table, Requirement entity
  and modular-monolith deployment boundary. No new service, table for results, Audit table or
  provider integration was introduced.
- All Requirement persistence predicates include Account and Project; Project soft deletion is
  honored before list/read/mutation.
- The migration adds only the approved nullable field and query index and has a reversible
  downgrade.

## Senior Review

- **Contract parity:** PASS. The implementation exposes only the approved collection, manual
  create, constrained patch/confirm and draft soft-deactivation behavior. Snapshot-dependent
  supersession, restore and UI remain deferred.
- **Tenant/security:** PASS. Every read and mutation is scoped by Account and Project, deleted
  Projects are excluded, active Membership is required and missing/cross-tenant resources share
  the safe 404 contract.
- **Concurrency/idempotency:** PASS. PATCH locks the target row and applies an `updated_at` CAS;
  creation reserves and completes the generic idempotency record in the same transaction. Exact
  replay performs no Requirement write, while changed input fails with 409.
- **Migration/query design:** PASS on PostgreSQL 16. The nullable column and descending
  tenant/project/time index migrated, downgraded and re-applied successfully. Repository ordering
  matches the index prefix and all destructive migration tests used a disposable database.
- **Observability/privacy:** PASS. Lifecycle, conflict and denial signals contain only approved
  identifiers/status metadata. Tests and the 532-file secret scan found no Requirement content or
  credential disclosure.
- **Architecture/scope:** PASS. The router remains thin, business behavior is in Application, SQL
  remains Infrastructure-only, and no new deployable, result store, audit table, Provider or
  Snapshot rule was introduced.

## Verification

- Focused Requirement Application/API suite: 12 passed.
- Focused Requirement regression suite: 59 passed.
- Requirement PostgreSQL suites on an isolated disposable PostgreSQL 16 container: 23 passed.
- I03 contract suite: 3 passed; API strict typecheck: 105 source files passed.
- Contract CI: 122 passed; Eval: 8 passed; Web: 19 passed; API: 347 passed; Worker: 57 passed.
- Full lint, strict typecheck and production build passed for Web, API and Worker.
- Mandatory `npm test`, `npm run validate`, secret scan and `git diff --check` passed; exact
  commands and results are recorded in the linked report.

## Remaining Risks

- Scope Snapshot-aware supersession remains deferred until that persistence/lifecycle contract is
  approved.
- Requirement UI and real browser validation remain I04.
- The API emits safe operational audit events; durable business audit-event persistence is not
  part of the approved I03 scope.
