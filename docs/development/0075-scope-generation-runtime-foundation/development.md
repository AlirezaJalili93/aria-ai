# Development Record: 0075 — Scope Generation Runtime Foundation

- **Status:** COMPLETE — controlled synthetic-only foundation
- **Increment:** AI-05 synthetic-only runtime foundation
- **Source sync date:** 2026-09-27
- [Test report](./test-report.md)

## Scope

Implement the accepted ADR-062 internal Job/Outbox/Worker foundation for AI-05. Public HTTP,
AI-04 chaining, customer content, real/paid Provider and hosted activation remain excluded.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K03; checked 2026-09-27.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-05; checked 2026-09-27.
- [ADR-041](../../adr/ADR-041-scope-draft-model.md), [ADR-042](../../adr/ADR-042-scope-readiness-policy.md), [ADR-043](../../adr/ADR-043-scope-generation-use-case.md), [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md), [ADR-062](../../adr/ADR-062-scope-generation-runtime-foundation.md).
- Owner's ADR-062 approval and input-mismatch clarification dated 2026-09-27.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-7501 | ADR-062 | Empty Context/Requirement preflight before AI and Usage | TC-7501, TC-7502 |
| REQ-7502 | ADR-042/062 | Shared pure K02 policy; open Critical blocks, dismissed does not | TC-7503 |
| REQ-7503 | ADR-041/043/062 | Draft conflict and atomic Draft/Job finalization | TC-7504, TC-7505 |
| REQ-7504 | ADR-057/062 | Job/Outbox, active-job index, identifier-only Queue delivery | TC-7504, TC-7506 |
| REQ-7505 | ADR-062 owner clarification | Sorted revision pinning and pre-commit recheck | TC-7508 |
| REQ-7506 | ADR-062 activation boundary | Synthetic allowlists and Fake Provider, absent from hosted composition | TC-7507 |
| REQ-7507 | Repository gate | Migration privilege review and full quality checks | TC-7509 |

## Assumptions and Clarifications

- `SCOPE_GENERATION_INPUT_CHANGED` with `retryable=false` is owner-approved.
- `max_attempts=1` satisfies the existing Jobs schema and is not an automatic retry policy.
- **Unapproved assumptions:** None

## Changes

- Accepted ADR-062, including the approved mismatch code and K02 authority correction.
- Added an internal synthetic-only scheduler. It pins sorted Context Item, Requirement and Gap
  `(id, updated_at)` vectors and commits one `scope_generation` Job with a matching Outbox event.
- Added the controlled `aria.scope.generate.v1` task, identifier-only Outbox mapping, Consumer,
  synthetic command factory, Fake AI and PostgreSQL snapshot/finalization adapters. Neither task
  nor Fake Provider is composed into the Hosted Worker.
- Added migration `0029_scope_generation_runtime`: partial unique active-Job index; named Draft
  INSERT and SELECT for `aria_worker` under RLS; no Draft UPDATE/DELETE. A fixed SECURITY DEFINER
  lock helper protects the short recheck transaction without broad input-table UPDATE authority.
- The finalizer rechecks pinned inputs and K02 state, validates K01's twelve-section content and
  trace, then inserts one Draft and marks the same Job succeeded in a single commit.
- Added contract, Application, Queue and isolated PostgreSQL tests, including Worker-role execution,
  changed input before/after Fake AI, duplicate delivery and forced-commit recovery.

## Structure Preservation

- Preserved internal Application scheduler → Job/Outbox ports ← API Infrastructure and controlled
  Celery task → Consumer → provider-neutral Scope use case → PostgreSQL ports.
- K01 Draft remains the sole working-Scope source of truth; K05 Scope Version stays separate.
- Shared K01/K02 pure modules preserve the prior API import surface and add no framework/Provider
  dependency to Domain or Application. No public route, new deployable or Hosted activation exists.
- Queue transport contains exactly `message_version`, `outbox_event_id`, `job_id`; no customer
  text, Requirement, Gap, Scope content or prompt enters its payload.

## Senior Review

- **Contract parity:** PASS. Empty eligible Requirements fail before AI/Usage. Only draft/confirmed
  Requirements are selected. Open Critical Gaps block; dismissed is non-blocking.
- **Atomicity/recovery:** PASS. Job/Outbox creation and Draft/Job success each use one transaction.
  Forced commit failure leaves no Draft and the same synthetic Job recoverable.
- **Concurrency/pinning:** PASS. PostgreSQL's partial unique index is the final active-Job guard.
  Revisions are checked before AI and under the finalization lock. An edit between Fake AI and
  commit returns `SCOPE_GENERATION_INPUT_CHANGED` with no Draft or Job success.
- **Least privilege:** PASS. A direct Worker table lock initially failed privilege checking; a
  no-data SECURITY DEFINER helper replaced it. The full flow then passed under `aria_worker`.
- **Privacy/activation:** PASS for this foundation. No hosted task registration, public endpoint,
  real Provider, paid invocation or customer-content path was introduced. Negative logging tests
  exclude Context/Requirement text and raw input.

## Verification

- PostgreSQL 16 isolated `aria_0075_test`: fresh upgrade, downgrade/re-upgrade of 0029,
  Worker-role privilege check and full controlled runtime path PASS.
- Full database-backed suites: API 605 passed/1 skipped; Worker 182 passed/1 skipped, followed by
  the added post-AI input-change test (5 focused Worker PostgreSQL tests PASS). The remaining
  skips are external-environment gates, not 0075 PostgreSQL cases.
- CI contracts 185, Eval 35, Web 40, 0075 runtime contracts 4 PASS. Full `npm test`, lint,
  typecheck, build, secret scan and `npm run validate` PASS. The default Python skip counts and
  non-blocking warnings are distinguished from the database-backed evidence in the test report.

## Remaining Risks

- Fake Provider PASS is orchestration evidence, not real-model quality or Product AI acceptance.
  Paid-call recovery, customer-data review and Hosted activation require separate gates.
- One API Hosted-upload and one Worker Redis test remain environment-gated; neither counts as
  PASS nor authorizes Hosted activation.
