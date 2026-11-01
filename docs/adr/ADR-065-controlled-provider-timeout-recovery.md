# ADR-065: Controlled Provider Timeout Recovery and Single Usage Writer

- **Status:** Accepted — owner approval 2026-09-28
- **Date:** 2026-09-28
- **Extends:** ADR-056, ADR-058 and ADR-063

## Decision

The isolated synthetic E2E-04 path runs one AI-01 Job through the existing
Provider Failure Coordinator. The first actual synthetic Provider invocation
returns a retryable `timeout` without reliable Usage. The bounded 0069 policy
performs one technical retry; the second invocation succeeds. No Fallback is
configured. Both attempts retain the same logical Job ID and have distinct
`provider_attempt_id` values.

For Coordinator-managed invocations, the Coordinator alone persists one
UsageRecord per actual invocation. The AI-01 Workflow consumes its normalized
result and does not append another UsageRecord. Existing direct-execution
Workflow paths retain their prior Usage writer. The integration must explicitly
declare and validate this single-writer mode; it cannot silently disable
metering on an unmarked execution port.

The first record is `failed / unavailable`, with NULL token and cost fields;
the second is `success / complete`. Exactly two actual invocations produce
exactly two durable records. Repeating persistence for the same attempt ID
remains idempotent under the existing unique constraint.

This path uses only synthetic fixtures and a Fake Provider in an isolated
test database under the actual `aria_worker` principal. It adds no public
route, runtime Primary/Fallback choice, customer-content path, paid call,
Hosted activation, Worker restart recovery or Queue redelivery semantics.
Ambiguous post-Provider persistence recovery remains deferred.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), E2E-04 and S1-L05; reread 2026-09-28.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), execution, retry and Usage boundary; reread 2026-09-28.
- Owner-approved 0079 contract and single-writer clarification, 2026-09-28.

**Unapproved assumptions:** None
