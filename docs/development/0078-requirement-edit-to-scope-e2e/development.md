# Development Record: 0078 Requirement Edit to Scope E2E

- **Status:** COMPLETE — isolated synthetic E2E-03 regression gate passed
- **Increment ID:** `0078-requirement-edit-to-scope-e2e`
- **Source sync date:** 2026-09-28
- [Test report](./test-report.md)

## Scope

Extend the approved isolated synthetic Context-to-Scope test harness with the
Sprint 1 E2E-03 case: edit one generated Requirement through the existing
authorized Application command before scheduling AI-05, then prove the new
Scope Draft uses that persisted revision. This is a test-only regression gate,
not a public workflow or product activation.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — E2E-03; reread 2026-09-28.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-REQ-002, TC-FE-005 and Context-to-Scope E2E; reread 2026-09-28.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-05 uses operational Requirements; reread 2026-09-28.
- [Sprint 1 Acceptance & Demo Plan](https://docs.google.com/document/d/1cNO4P5hBIzgQAvNVAnOdfI84IyTQj8UXxdN9GfGvb1Y/edit) — human edit and Scope consistency; reread 2026-09-28.
- [ADR-032](../../adr/ADR-032-requirement-crud-contract.md), [ADR-062](../../adr/ADR-062-scope-generation-runtime-foundation.md), [ADR-063](../../adr/ADR-063-controlled-synthetic-context-to-scope-integration.md) — accepted existing commands and isolated synthetic boundary.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-7801 | Backlog E2E-03; ADR-032 | Controlled harness invokes `RequirementCrudService.update` after AI-02, never direct SQL mutation | TC-7801 |
| REQ-7802 | ADR-062; AI-05 Workflow | AI-05 Job pins the edited Requirement revision and Scope Draft requirement section reflects its persisted title and ID | TC-7802 |
| REQ-7803 | ADR-063; 0077 approved boundary | Separate scenario reuses throwaway PostgreSQL, local Relay/Queue, actual `aria_worker` and Fake Providers; baseline scenario remains unchanged | TC-7803 |
| REQ-7804 | Test Strategy privacy/isolation; ADR-063 | No customer text, real Provider, hosted execution, fixture text in logs, or content in Queue envelope | TC-7804 |

## Assumptions and Clarifications

- The edited title is a versioned synthetic fixture value, not a product rule.
- **Unapproved assumptions:** None

## Changes

- Added immutable `requirement_edit_to_scope_synthetic_fa_v1` test data with a
  stable fixture ID and one Persian edited title.
- Added an opt-in `--requirement-edit` scenario to the existing controlled
  harness. After AI-02, it reads the tenant/project/version-scoped generated
  Requirement, edits through `RequirementCrudService.update` with CAS, and
  verifies a stale second edit is rejected without overwriting the new value.
- The scenario explicitly runs AI-03 and AI-05 through their existing
  Job/Outbox/Relay/Worker path. It checks the AI-05 Job's exact pinned
  Requirement revision and the Draft's Requirements section value and trace.
- Added `npm run test:requirement-edit-to-scope-e2e`; it first reruns the
  unchanged 0077 baseline and PostgreSQL negative gates, then the new scenario.
  The API/Worker diagnostic boundaries keep fixture text out of output.

## Structure Preservation

PASS. Changes are limited to `tests/e2e/`, one test command in `package.json`
and this increment's two Markdown records. No production composition, public
endpoint, schema, Domain contract, hosted activation or automatic chaining
changed. Existing 0077 default behavior remains separately executable and
passed again. No new ADR was needed because no consequential architecture
decision changed; accepted ADR-032/062/063 boundaries were exercised as-is.

## Senior Review

- **Contract parity:** PASS. The edit uses the authorized Requirement
  Application command, retains the same ID/Context Version, advances
  `updated_at`, and stale CAS fails. AI-05 pins that exact revision before
  execution, rather than selecting a later or original Requirement silently.
- **Data and tenant safety:** PASS for this isolated gate. All new test queries
  are bounded by Account, Project and Context Version. The existing throwaway
  database guard and actual `aria_worker` path remain in force. No direct SQL
  mutation of Requirement or Gap state was added.
- **Privacy and scope:** PASS. The edited fixture title is prohibited from
  API/Worker logs and process output. Queue messages remain identifier-only.
  Fake Providers and synthetic data cannot establish real-model quality.
- **Corrections during review:** Added stale-CAS coverage, extended Worker
  leakage checks to the new edited title, and changed the API diagnostic
  boundary to emit only a safe exception class while retaining a specific
  pre-migration non-test-database guard assertion.

## Verification

See [test-report.md](./test-report.md). The final controlled 0078 gate passed
under `aria_worker`, including the unchanged 0077 baseline and 4 API + 9
Worker PostgreSQL negative cases. `npm test` passed (API 608 passed/1
hosted-only skip; Worker 188 passed/0 skipped). Lint, typecheck, focused
Ruff/compile checks and `npm run validate` passed.

## Remaining Risks

- This controlled Fake Provider gate cannot establish real-model quality,
  customer-data readiness, hosted activation, or full Login-to-Scope acceptance.
