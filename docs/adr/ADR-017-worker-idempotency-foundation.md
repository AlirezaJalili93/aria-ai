# ADR-017: Worker Idempotency Foundation

- Status: Accepted
- Date: 2026-09-05
- Scope: S1-E04 foundation only

## Context

The accepted Queue evaluation establishes at-least-once delivery. PostgreSQL Jobs remain the
operational Source of Truth; Queue/Redis is not canonical. S1-E04 requires duplicate delivery not to
create duplicate committed business effects, but the repository does not yet define a Job claim/lease,
task handler, artifact schema, timeout, retry or transport acknowledgement contract.

## Decision

- Worker Application exposes a provider-neutral `JobExecutionGuard` keyed only by `job_id`.
- Atomic `acquire(job_id)` returns exactly `acquired`, `already_in_progress` or `already_completed`.
  Two concurrent deliveries must not both receive `acquired`; the storage mechanism is deferred.
- A successful acquired handler calls `complete(job_id)` through the same guard boundary.
- `already_completed` is a successful no-op and does not invoke the handler.
- `already_in_progress` suppresses duplicate execution in this increment; Queue ACK/requeue/retry
  semantics are not selected.
- Interrupted execution is observable and does not call `complete`. Recovery behavior is demonstrated
  only by a repository fixture; no stale-running duration or lease is invented.
- Business-state/artifact uniqueness remains a separate invariant for each future Job story. The guard
  alone is not a substitute for a business write constraint.

## Deferred boundaries

PostgreSQL lock/claim implementation, schema changes, Job lifecycle semantics, stale-running policy,
execution timeout, retry/backoff/exhausted behavior, Celery task registration, ACK/requeue and
artifact-specific deduplication require later approved contracts.

## Consequences

- Duplicate suppression can be tested now without coupling Worker Application to Celery, Redis or
  SQLAlchemy.
- No second Worker idempotency table or competing Source of Truth is introduced.
- Future infrastructure must implement the atomic port against PostgreSQL before production Worker
  execution is enabled.
