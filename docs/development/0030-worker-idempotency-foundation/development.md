# Development Record: 0030 Worker Idempotency Foundation

[Test report](./test-report.md)

## Scope

- Increment ID: `0030-worker-idempotency-foundation`
- Story: `S1-E04 — Worker Idempotency`, foundation slice
- Status: Completed
- Scope: provider-neutral `JobExecutionGuard`, atomic acquisition contract, duplicate suppression,
  completion transition, interruption telemetry and fake repository recovery proof.
- Explicitly deferred: PostgreSQL lock/claim implementation, schema changes, second idempotency table,
  Job lifecycle/stale-running policy, timeout, retry/backoff/exhausted behavior, Celery ACK/requeue,
  task registration and artifact-specific deduplication.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-E04 acceptance; read 2026-09-05.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit?usp=drivesdk) — Worker recovery and no duplicate outcome gate; read 2026-09-05.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit?usp=drivesdk) — TC-JOB-005/008 and async recovery requirements; read 2026-09-05.
- [ADR-002 — Async Pipeline](../../architecture/decisions/ADR-002-async-pipeline.md)
- [ADR-015 — Durable Queue Framework](../../adr/ADR-015-durable-queue-framework.md)
- [ADR-017 — Worker Idempotency Foundation](../../adr/ADR-017-worker-idempotency-foundation.md)
- [Repository instructions](../../../AGENTS.md)

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3001 | S1-E04; ADR-017 | `JobExecutionGuard` Application port keyed only by `job_id` | TC-3001 |
| REQ-3002 | Owner approval 2026-09-05; ADR-017 | Atomic acquisition result vocabulary: `acquired`, `already_in_progress`, `already_completed` | TC-3001, TC-3002 |
| REQ-3003 | S1-E04; system architecture | Duplicate statuses do not invoke the business handler | TC-3002, TC-3003 |
| REQ-3004 | S1-E04; Test Master TC-JOB-008 | Interrupted execution does not mark completion; fixture can recover and execute once | TC-3004 |
| REQ-3005 | S1-A04; owner approval | Approved Worker guard telemetry without payload/artifact content | TC-3005 |
| REQ-3006 | Owner approval; ADR-017 | No new table, claim strategy, timeout, retry, ACK/requeue or artifact schema | TC-3001, TC-3006 |

## Changes

- Added `JobExecutionGuard` with atomic acquisition and explicit completion contracts.
- Added `JobExecutionCoordinator` that suppresses `already_in_progress` and treats
  `already_completed` as a successful no-op.
- Added interruption handling that emits telemetry and deliberately avoids completion.
- Bound worker logs to approved `job_id`, account/project/correlation context and safe task type.
- Added ADR-017 and updated the durable queue evaluation plan.
- Updated Worker task documentation to distinguish the foundation from future task handlers.
- Added contract and unit tests before final verification.

## Structure Preservation

- Worker Application contains only provider-neutral ports and orchestration.
- No Celery, Redis, SQLAlchemy or asyncpg import was added to the Application boundary.
- No migration, Worker idempotency table or second Source of Truth was introduced.
- Existing Celery runtime remains configuration-only; business task registration remains deferred.
- Business artifact constraints remain owned by future Job-specific stories.

## Senior Review

- PASS: Guard key is exactly `job_id`.
- PASS: Caller-visible acquisition vocabulary matches the approved contract.
- PASS: Duplicate decisions prevent handler invocation; completed duplicates are no-op success.
- PASS: Interrupted execution never calls `complete`; recovery timing is not invented.
- PASS: Queue ACK/requeue/retry semantics are absent from this increment.
- PASS: Telemetry excludes payload, prompt, raw input and artifact content.
- PASS: No unapproved storage or lock implementation was selected.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The owner approved the limited E04 foundation on 2026-09-05. `complete(job_id)` is the minimal
completion transition required to make the approved `already_completed` outcome meaningful; its
storage and atomicity implementation remain deferred with the Job claim contract.

## Verification

See [test-report.md](./test-report.md). Worker unit/contract tests, full repository tests, lint,
type checking, build and architecture validation passed. Existing Windows pytest cache warnings remain
non-blocking.

## Remaining Risks

- Production Worker execution cannot be enabled until an accepted PostgreSQL claim/lock adapter and
  Job lifecycle contract implement this port.
- Stale `running` recovery, timeout, retry/backoff and exhausted behavior remain open.
- Each business Job must add its own committed state/artifact uniqueness invariant.

**Final status:** PASS
