# Development Record: 0074 — Gap Detection Runtime Foundation

- **Status:** COMPLETE
- **Increment:** S1-J02 runtime foundation
- **Source sync date:** 2026-09-22
- [Test report](./test-report.md)

## Scope

Implement the approved internal, synthetic-only AI-03 Job/Outbox/Worker foundation with exact
Context/Requirement revision binding, valid empty Requirement input and deterministic Critical
Gap evaluation. Public API, workflow chaining, customer content, paid Providers and hosted
activation remain outside this increment.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J02
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03
- [ADR-036](../../adr/ADR-036-gap-detection-foundation.md)
- [ADR-037](../../adr/ADR-037-gap-critical-rule-pack.md)
- [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md)
- [ADR-061](../../adr/ADR-061-gap-detection-runtime-foundation.md)
- Owner-approved 0074 contract dated 2026-09-22.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-7401 | 0074 contract | Internal synthetic-only scheduling boundary | TC-7401, TC-7408 |
| REQ-7402 | ADR-036/037 | Exact Context/Requirement/policy version pinning | TC-7401, TC-7404 |
| REQ-7403 | 0074 clarification | Empty Requirement set remains valid | TC-7401, TC-7404 |
| REQ-7404 | ADR-057 | Identifier-only Outbox/Queue/Celery delivery | TC-7402, TC-7403 |
| REQ-7405 | ADR-036/037 | Fake AI-03 plus authoritative deterministic Rule Pack | TC-7404 |
| REQ-7406 | 0074 contract | Atomic Gap/link/rule-result/Job finalization | TC-7405, TC-7406 |
| REQ-7407 | Safety boundary | No public/chained/hosted/real-Provider path | TC-7407, TC-7408 |
| REQ-7408 | Repository gate | Documentation, Senior review and full verification | TC-7409 |

## Assumptions and Clarifications

- Empty Requirement set is a valid AI-03 input and must not create a synthetic generic
  no-Requirement Gap.
- Missing or unusable Context is an explicit precondition failure.
- **Unapproved assumptions:** None

## Changes

- Added an internal scheduler gated by an explicit synthetic Project allowlist. It pins one
  Context Version, sorted Context Item and Requirement revision vectors, and the approved Checklist
  and Critical Rule Pack versions. An empty Requirement vector remains valid; missing usable
  Context is rejected.
- Added atomic creation of a `gap_detection` Job and `gap.detection_requested.v1` Outbox event.
  The Queue envelope contains only `message_version`, `outbox_event_id` and `job_id`.
- Added a controlled `aria.gaps.detect.v1` task registration, Consumer, exact Job/Outbox validation,
  PostgreSQL snapshot and Unit-of-Work adapters, and a deterministic synthetic AI-03 adapter.
  Hosted Worker composition does not register the task.
- Added migration `0028_gap_detection_runtime` with a partial unique active-Job index and
  insert-only Worker authority for Gap and Gap/Requirement link writes. Gap rows, links, rule
  results and Job success finalize in one transaction.
- Added contract, Application, Queue and real PostgreSQL tests. The PostgreSQL fixture was
  corrected during verification to use a valid `proposed` Fact with no provenance; the database
  correctly rejects a `confirmed` Fact without provenance.
- Synchronized ADR-061 and the architecture, Migration, Worker and development indexes.

## Structure Preservation

- Preserved `internal Application scheduler → Job/Outbox ports ← SQLAlchemy Infrastructure` and
  `controlled Celery task → Consumer → provider-neutral Gap use case → PostgreSQL ports`.
- Domain/Application code contains no Celery, SQLAlchemy, Redis or concrete Provider SDK import.
- The Worker resolves tenant and exact snapshot state from PostgreSQL by Job ID. Outbox and Queue
  messages carry no Context, Requirement, Gap, prompt or customer content.
- No public route, AI-02 chaining, hosted task registration, new deployable or runtime Provider
  promotion was introduced.

## Senior Review

- **Contract parity:** PASS. Empty Requirements are valid; usable Context and exact revisions are
  mandatory. Checklist-backed Critical rules remain authoritative, and the Fake Provider does not
  synthesize a generic missing-Requirement Gap.
- **Atomicity and recovery:** PASS. Job/Outbox creation is atomic. Gap/link/rule-result writes and
  Job success commit together; forced commit failure leaves zero Gap rows and the same Job
  recoverable. Duplicate delivery becomes a no-op after completion.
- **Concurrency:** PASS. PostgreSQL's partial unique index prevents two active Jobs for one
  Account/Project/Context Version; the execution guard suppresses concurrent Worker execution.
- **Tenant and privilege boundary:** PASS. Snapshot and replay queries are Account/Project scoped,
  Job and Outbox identities are cross-checked, and composite Gap/link constraints preserve tenant
  linkage. Worker has SELECT and named INSERT columns on Gaps; UPDATE/DELETE remain denied. RLS is
  enabled on the Gap table.
- **Privacy and cost:** PASS for this foundation. The task is absent from hosted composition,
  synthetic fixture access is explicitly gated, the adapter reports zero tokens/cost, and Queue
  payloads and structured logs exclude customer content.
- **Migration:** PASS. Fresh PostgreSQL 16 upgrade, downgrade to 0027 and re-upgrade to 0028 passed.
  The final Worker privilege projection was checked on the isolated test database.

## Verification

- Runtime contract: 6 passed. Focused API: 24 passed; focused Worker: 16 passed.
- Isolated PostgreSQL: 12 API tests and 2 Worker tests passed, including zero Requirements,
  checklist-backed Gaps, duplicate suppression and commit recovery.
- `npm test` passed: CI contracts 185, Eval 35, Web 40, API 447 passed/151 skipped, Worker 154
  passed/16 skipped. Skipped PostgreSQL cases in the default suite were run separately against the
  isolated database.
- Web/API/Worker lint and strict typecheck passed; production build and secret scan passed.
- Mandatory `npm run validate` and `git diff --check` passed in the final documented run; exact
  commands and actual results are in the linked test report.

## Remaining Risks

- The deterministic Fake Provider tests orchestration and the rule pipeline, not real Gap quality.
  Real Provider evaluation, customer-data review and paid-call recovery require separate gates.
- Hosted activation and a public trigger remain deferred; this foundation is not yet a Product AI
  feature in Staging.
- Queue-level automatic retry remains disabled. Recovery demonstrated with a Fake Provider does
  not authorize re-invoking a paid Provider after an ambiguous persistence failure.
