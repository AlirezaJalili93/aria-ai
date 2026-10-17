# Development Record: 0085 Durable Technical-Retry Checkpoint Integration

- Increment ID: `0085-durable-technical-retry-checkpoint-integration`
- Date: 2026-09-30
- Owner: Platform/Worker Engineering
- Related workflow: `AI-01 — Context Structuring`
- [Test report](./test-report.md)

## Scope

Extend the synthetic AI-01 durable checkpoint with exactly one known-timeout Technical Retry.
Persist Attempt 0 failure, unavailable Usage and one retry schedule atomically; survive restart
without repeating Attempt 0; create at most one Attempt 1; retain ADR-070 atomic result and Domain
finalization. Do not enable Repair, Fallback, Queue automatic retry, real Providers, customer
content or Hosted execution.

## Source Documents

- Owner-approved frozen `0085 — Durable Technical-Retry Checkpoint Integration` contract,
  2026-09-30.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — Retry, Usage and recovery gates; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — bounded retry, jitter, Usage and failure semantics; reread 2026-09-30.
- [ADR-056](../../adr/ADR-056-ai-failure-policy.md),
  [ADR-069](../../adr/ADR-069-durable-ai-invocation-recovery.md),
  [ADR-070](../../adr/ADR-070-ai01-durable-checkpoint-integration.md) and
  [ADR-071](../../adr/ADR-071-durable-technical-retry-checkpoint-integration.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8501 | Owner 0085 §1/6 | `failed_known` is distinct from terminal `outcome_unknown`; only timeout is eligible | TC-8501, TC-8506 |
| REQ-8502 | Owner 0085 §2 | Distinct Attempt IDs and one Usage row per actual invocation | TC-8502, TC-8504 |
| REQ-8503 | Owner 0085 §3 | Full Jitter is calculated once and persisted as `retry_not_before` | TC-8502, TC-8503 |
| REQ-8504 | Owner 0085 §4 | Restart reuses Attempt 0 failure/schedule and creates only Attempt 1 | TC-8503, TC-8505 |
| REQ-8505 | Owner 0085 §5 | Maximum two Primary attempts; no Repair or Fallback | TC-8501, TC-8502 |
| REQ-8506 | Owner 0085 §7 | Known failure, unavailable Usage and schedule share one transaction | TC-8502, TC-8507 |
| REQ-8507 | Owner 0085 Gate | Pinned fingerprint, cross-Tenant denial, safe telemetry and atomic finalization | TC-8503, TC-8506, TC-8508 |

## Assumptions and Clarifications

The owner froze timeout as the only 0085 known-retry failure, two total Primary attempts, no
schedule for Attempt 1, persisted Full Jitter, distinct attempt identities and atomic Usage.
Existing raw Worker SELECT policy remains out of scope.

**Unapproved assumptions:** None

## Changes

- Added ADR-071 and Migration 0033 for `failed_known` metadata, state coherence, transition
  enforcement, retry-due indexing and safe downgrade refusal.
- Extended the provider-neutral checkpoint contract with known-failure persistence and recovery.
- Added opt-in synthetic AI-01 timeout orchestration with injected Clock, Random and Sleeper.
- Added concurrency-safe Attempt creation using the existing logical-attempt unique index.
- Kept timeout Usage honest with `NULL` tokens/cost and `accounting_status=unavailable`.
- Added static, unit and actual-`aria_worker` PostgreSQL crash/recovery tests.

## Structure Preservation

- Application code remains free of SQLAlchemy, Celery and Provider SDK imports.
- PostgreSQL transaction and RLS details remain in Worker Infrastructure.
- Existing single-attempt checkpoint mode remains the default; retry is opt-in and synthetic-only.
- No endpoint, Queue task, deployable service, Provider mapping or Hosted composition was added.
- Queue/Outbox envelopes and logging remain content-free.

## Senior Review

- PASS: `failed_known` and `outcome_unknown` have disjoint transitions and recovery semantics.
- PASS: retry schedule is durable and no Attempt 1 is created before eligibility.
- PASS: duplicate redeliveries resolve to one logical Attempt 1 at the database constraint.
- PASS: timeout Usage and checkpoint state commit or roll back together.
- PASS: recovery retains the same Job and exact input fingerprint without repeating Attempt 0.
- PASS: Attempt 1 success retains ADR-070 atomic Domain finalization.
- PASS: excluded real/paid/customer/Hosted paths remain absent.

## Verification

See [test-report.md](./test-report.md). The isolated PostgreSQL 16 gate passed under the actual
`aria_worker` principal. Repository-wide tests, lint, typecheck, production build, architecture
validation and secret scanning all passed in the final verification run.

## Remaining Risks

- Semantic Repair and Fallback checkpoint integration remain deferred.
- Known `rate_limited` and `provider_unavailable` durable retry remain outside 0085.
- Real Provider, customer-content and Hosted activation remain blocked by separate release gates.

**Final status:** PASS
