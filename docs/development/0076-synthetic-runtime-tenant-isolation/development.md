# Development Record: 0076 — Synthetic Runtime Tenant Isolation

- **Status:** COMPLETE — local security regression extension
- **Increment:** S1-L03 regression extension for AI-02/AI-03/AI-05 internal runtimes
- **Source sync date:** 2026-09-27
- [Test report](./test-report.md)

## Scope

Extend the approved Tenant A/B PostgreSQL security suite to the synthetic-only internal
Requirement, Gap and Scope generation runtimes introduced in 0073–0075. This is test-only:
no new endpoint, Worker task registration, product behavior, schema, grant or Provider is added.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — every tenant-aware Story requires a cross-tenant test; S1-L03; reread 2026-09-27.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — tenant-scoped resource query and Worker revalidation; reread 2026-09-27.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — simultaneous Tenant A/B fixtures, security regression and real PostgreSQL; reread 2026-09-27.
- [ADR-048](../../adr/ADR-048-cross-tenant-security-suite.md), [ADR-060](../../adr/ADR-060-requirement-generation-runtime-foundation.md), [ADR-061](../../adr/ADR-061-gap-detection-runtime-foundation.md), [ADR-062](../../adr/ADR-062-scope-generation-runtime-foundation.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-7601 | Backlog S1-L03; Test Strategy Tenant A/B | `apps/api/tests/test_synthetic_runtime_tenant_isolation_postgres.py` | TC-7601 |
| REQ-7602 | Access Control tenant-scoped reads; ADR-048 | `apps/api/tests/test_synthetic_runtime_tenant_isolation_postgres.py` | TC-7602 |
| REQ-7603 | Access Control Worker ownership revalidation; ADR-060/061/062 | `apps/worker/tests/test_synthetic_runtime_tenant_isolation_postgres.py` | TC-7603 |
| REQ-7604 | Test Strategy no partial effects; ADR-060/061/062 | Both PostgreSQL regression test files | TC-7604 |

## Assumptions and Clarifications

- Synthetic allowlists in the API tests explicitly include attempted project IDs to expose
  the actual tenant-scoped PostgreSQL lookup. This is test configuration, not runtime exposure.
- A forged foreign-Tenant Outbox event is seeded only in an isolated test database by the
  test owner role. No public mechanism can create it.
- **Unapproved assumptions:** None

## Changes

- Added a two-Tenant API regression for AI-02/03/05 scheduling. A valid project of Tenant A
  and an unknown project produce the same internal context-required result under Tenant B;
  no Job or Outbox event is created.
- Added a two-Tenant Worker persistence regression under the actual `aria_worker` role. A
  foreign-Tenant Outbox ID paired with Tenant A's Job ID is rejected before Job state changes
  for AI-02/03/05.

## Structure Preservation

- No existing application or database implementation is modified.
- The established scheduler, Job/Outbox, Worker and RLS boundaries remain unchanged.
- The test does not introduce a public route, automatic chaining, customer content or
  real/paid Provider invocation.

## Senior Review

- **Contract parity:** PASS. Both Tenant fixtures are present concurrently; the synthetic
  allowlist does not mask the tenant-scoped query under test.
- **Security:** PASS. Foreign and missing Project IDs produce the same internal denial for
  all three schedulers. A foreign Outbox cannot enter Job preparation under `aria_worker`.
- **Atomicity:** PASS. Rejections leave zero new Job/Outbox rows and leave an existing Job queued
  with `attempt_count=0`; no Requirement, Gap or Draft is generated.
- **Privacy/structure:** PASS. Fixtures contain only synthetic text. No public surface,
  Provider wiring, schema or privilege change was introduced.

## Verification

- Focused PostgreSQL suites: API 3 passed; Worker 3 passed.
- Full PostgreSQL suites: API 608 passed/1 skipped; Worker 186 passed/1 skipped after correcting
  the local test URL to specify the `asyncpg` driver.
- Full repository quality-gate results are recorded in the linked test report.

## Remaining Risks

- These tests cover internal synthetic execution boundaries, not the still-prohibited
  customer/paid/hosted AI activation or complete Login-to-Scope product E2E journey.
