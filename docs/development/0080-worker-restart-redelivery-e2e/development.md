# Development Record: 0080 Worker Restart and Redelivery E2E

- **Status:** COMPLETE — controlled pre-Provider Worker restart gate passed
- **Increment ID:** `0080-worker-restart-redelivery-e2e`
- **Source sync date:** 2026-09-28
- [Test report](./test-report.md)

## Scope

Prove Sprint E2E-05 at the approved pre-Provider checkpoint through the real local
HTTP/Outbox/Relay/Celery/Worker/PostgreSQL path. Worker #1 is hard-killed after the original Job is
durably running and before Provider invocation; Worker #2 must recover the same unacknowledged
delivery and finish the same Job without duplicate effects. Post-Provider ambiguity, real/paid
Providers, customer data and Hosted activation are out of scope.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-E02, E2E-05 and Queue restart DoD; reread 2026-09-28.
- [Test Strategy v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-JOB-008 and L5 recovery coverage; reread 2026-09-28.
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — Durable Async Worker and PostgreSQL Job authority; reread 2026-09-28.
- [ADR-015](../../adr/ADR-015-durable-queue-framework.md), [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md), [ADR-058](../../adr/ADR-058-context-structuring-job-runtime-foundation.md), [ADR-066](../../adr/ADR-066-worker-restart-redelivery-gate.md).
- Owner-approved frozen 0080 contract, 2026-09-28.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-8001 | Backlog S1-E02/E2E-05; ADR-015/066 | Actual Celery late-ack delivery and hard Worker restart harness | TC-8001 |
| REQ-8002 | Owner 0080; ADR-066 | Deterministic test-only post-prepare/pre-Provider failpoint | TC-8002 |
| REQ-8003 | Owner 0080; ADR-058/066 | Same running Job reclaim via session advisory lock and Worker #2 | TC-8003 |
| REQ-8004 | Owner 0080; ADR-066 | Zero pre-crash and exactly one post-recovery Provider invocation/UsageRecord | TC-8004 |
| REQ-8005 | ADR-058/066 | Synthetic-only, no customer/paid/Hosted boundary and leakage assertions | TC-8005 |

## Assumptions and Clarifications

- The owner froze the exact crash checkpoint after guard acquisition and durable `running`, but
  before Provider invocation.
- Broker redelivery of the unacknowledged message is distinct from automatic Celery task retry,
  which remains disabled.
- **Unapproved assumptions:** None

## Changes

- Accepted ADR-066 and linked it from the ADR index.
- Added an isolated real-Celery harness that composes the accepted Queue adapter,
  `aria.context.structure.v1` task, PostgreSQL advisory Job guard, durable Usage Ledger and
  synthetic AI-01 runtime. Hosted Worker composition remains unchanged.
- Added a deterministic test-only Job-store failpoint immediately after durable `running` and
  before command construction/Provider invocation. The failpoint writes only bounded IDs and then
  blocks until Worker #1 is hard-killed.
- Added a PowerShell recovery runner that creates the command through the actual FastAPI route,
  publishes its Outbox event through the real Relay, proves a concurrent guard cannot acquire the
  Job, force-kills Worker #1, starts Worker #2 and verifies broker redelivery and final state.
- Added persisted synthetic zero-price setup only for this controlled Usage assertion, exact
  Provider invocation markers, contract tests and `npm run test:worker-restart-e2e`.

## Architecture and Design Decisions

See ADR-066. Broker redelivery of an unacknowledged delivery is not Celery automatic retry.
The existing product configuration remains late-ack, reject-on-worker-loss and prefetch-one, while
the task's `autoretry_for` remains empty. The five-second visibility timeout and Windows `solo`
pool are isolated test fixtures, not product defaults. No product retry policy, schema, service,
route or Hosted composition is introduced.

## Structure Preservation

PASS. The modular-monolith, HTTP/Application/Infrastructure layering, transactional Outbox,
identifier-only Queue envelope, PostgreSQL Job authority, advisory-lock guard, Usage ownership and
atomic Context finalization are preserved. All failpoint and invocation-marker code lives in
`tests/e2e`; `apps/worker/app/main.py` still does not register the synthetic AI-01 task. No
migration, grant, RLS policy, real Provider or customer-data path was added.

## Senior Review

- **Recovery correctness:** PASS. Worker #1 held the advisory lock and the same Job was durably
  `running`; an independent Worker-role probe received `already_in_progress`. Hard process death
  closed the session, and Worker #2 reclaimed the same running Job after broker redelivery.
- **Provider/accounting boundary:** PASS. The deterministic checkpoint proved zero Provider
  invocation markers and zero Usage rows before kill. Recovery produced exactly one marker, one
  distinct `provider_attempt_id`, one Usage row and one successful Job.
- **Idempotency/atomicity:** PASS. Job and Outbox counts remained one, `attempt_count` remained one,
  Project Context Version advanced once and one Context Item at one Context Version was committed.
- **Privacy/activation:** PASS. Queue payload remained identifier-only; Worker process output did
  not contain the synthetic source marker. Hosted composition, real/paid Provider and customer
  content remain disabled.
- **Corrections during review:** Split a PostgreSQL query bind into UUID and text parameters after
  asyncpg correctly rejected a mixed-type bind. The final real recovery run passed. The first
  fresh-secondary-database attempt also exposed a pre-existing cluster-global Role creation issue
  in migration 0030; it was not hidden or changed in this increment and is recorded below.

## Verification

See [test-report.md](./test-report.md). The real 0080 gate, contract tests, full `npm test`, lint,
typecheck, build and secret scan passed. `npm run validate` passed after these records were
finalized.

## Remaining Risks

- Migration 0030 creates cluster-global `aria_generation_lock_owner` without an existence guard.
  A second fresh database in the same PostgreSQL cluster therefore failed at that migration when
  the Role already existed. The half-created throwaway `aria_0072_test_0080` database was removed;
  the final 0080 Gate used the existing dedicated, fully migrated `aria_0077_test`. This is a
  separate migration-safety concern and remains a Sprint fresh-database release risk until an
  approved remediation is implemented.
- Crash during Provider execution or after Provider success but before durable persistence remains
  intentionally deferred. This synthetic local gate does not authorize customer, paid or Hosted
  activation.
