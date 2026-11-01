# ADR-071 — Durable Technical-Retry Checkpoint Integration

- Status: Accepted
- Date: 2026-09-30
- Decision owner: Product and Engineering
- Extends: ADR-056, ADR-069 and ADR-070

## Context

ADR-070 integrated one durable AI-01 Provider attempt but intentionally disabled Technical Retry.
ADR-056 permits one bounded Primary retry with Full Jitter. An in-memory delay is insufficient:
after a known timeout, Worker restart or Queue redelivery could repeat Attempt 0, calculate a new
delay, duplicate Usage or exceed the invocation budget.

## Decision

0085 adds an opt-in, synthetic-only AI-01 timeout-retry mode. It supports exactly two Primary
attempts (`retry_no=0` and `retry_no=1`), no Semantic Repair and no Fallback. Only the known
`timeout` failure class may enter this path.

### Known failure and ambiguous outcome

`failed_known` means the Provider outcome is known to be a retryable timeout. The checkpoint,
failed UsageRecord and `retry_not_before` commit atomically. `outcome_unknown` remains terminal for
automatic invocation and can never transition back to `started` or `failed_known`.

Attempt 0 receives a persisted Full-Jitter schedule calculated once from the ADR-056 formula. A
restart reads that timestamp and neither recalculates nor extends it. Attempt 1 cannot be created
before eligibility. Attempt 1 failure is terminal for this execution and has no retry schedule.

### Identity, concurrency and accounting

Retry uses the same Job, Account, Project, Workflow/Prompt/schema versions and exact AI-01 input
fingerprint. Each actual invocation has a distinct `provider_attempt_id`. The existing unique
logical-attempt index is the final PostgreSQL race guard: concurrent redeliveries can create at
most one row for Attempt 1.

One invocation creates exactly one UsageRecord. A timeout without trustworthy Provider usage is
recorded as `failed/unavailable` with token and cost fields `NULL`; zero is never fabricated.
The successful Attempt 1 checkpoint and UsageRecord commit atomically, then ADR-070 Domain
finalization remains recoverable and atomic.

### Activation boundary

The integration is opt-in, Fake-Provider and synthetic-data only. Queue automatic retry remains
disabled. Semantic Repair, Fallback, real or paid Providers, customer content and Hosted
activation are excluded.

## Consequences

- Crash after `failed_known` resumes the same Job without reinvoking Attempt 0.
- Persisted jitter survives restart and exactly two invocations produce exactly two Usage rows.
- Pinned-input mismatch and ambiguous `started` checkpoints fail closed.
- The single-attempt ADR-070 mode remains available when durable timeout retry is not enabled.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), Retry, Usage and recovery gates; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), bounded retry, jitter, Usage and failure semantics; reread 2026-09-30.
- Owner-approved frozen `0085 — Durable Technical-Retry Checkpoint Integration` contract,
  2026-09-30.

**Unapproved assumptions:** None
