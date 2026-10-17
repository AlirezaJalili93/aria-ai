# ADR-056 — Bounded AI Failure, Retry and Fallback Capability

- Status: Accepted
- Date: 2026-09-20
- Decision owner: Product and Engineering
- Extends: ADR-021, ADR-022, ADR-024, ADR-027 and ADR-055

## Context

S1-L05 requires deterministic tests for Provider timeout, invalid JSON, technical retry, fallback
and duplicate-cost prevention. The canonical AI Workflow requires bounded backoff with jitter,
separate Retry and Repair accounting, conditional fallback and one Usage record per paid
invocation. Earlier ADRs deliberately left the numeric retry schedule, fallback capability and
unknown-usage representation unresolved.

## Decision

### Technical retry

- Application owns technical retry. Provider SDK retries remain disabled.
- Primary has at most two actual invocations: initial `retry_no=0`, then one optional retry with
  `retry_no=1`.
- Only `timeout`, `rate_limited` and `provider_unavailable` are technically retryable, and the
  mapped error must also declare `retryable=true`.
- Full Jitter uses a ceiling of `min(4s, 1s * 2^retry_no)`. Clock, sleeper and random source are
  injectable; deterministic tests perform no wall-clock sleep.
- Unparseable structured output is `invalid_response` and receives no technical retry or fallback.
  Parsed but schema-invalid output remains eligible only for the independent bounded Semantic
  Repair contract. Business validation failure is not a technical retry.

### Fallback capability

- Primary candidate: none.
- Fallback candidate: none.
- 0069 adds Provider-neutral capability and deterministic synthetic tests only; it does not wire a
  runtime route or promote either evaluation candidate from ADR-055.
- Fallback is considered only after both Primary invocations fail and the final failure is
  `timeout` or `provider_unavailable`. `rate_limited` never triggers fallback in Sprint 1.
- An explicit `FallbackAuthorizationPort` decision must allow both quality and budget. Missing
  policy, policy exception or either denial fails closed without a Fallback invocation.
- An authorized Fallback receives exactly one invocation, never a retry. Its failure is terminal
  for the execution. Maximum total Provider invocations are therefore three.

### Usage and cost integrity

- `provider_attempt_id UUID NOT NULL UNIQUE` identifies one actual Provider invocation. A
  persistence retry reuses the same ID; a real technical retry or Fallback call receives a new ID.
- The Worker Ledger adapter performs `INSERT ... ON CONFLICT DO NOTHING` for that identifier, so
  persistence replay cannot duplicate cost.
- `accounting_status` is `complete` or `unavailable`. Complete records require token counts and
  estimated cost. Unavailable records require `status=failed` and NULL input, cached-input, output
  and estimated-cost fields. Zero must never represent unknown Usage.
- Price identity is still resolved before every paid invocation. A timeout without Provider Usage
  retains that Price Version but records unknown token/cost values honestly.
- Ledger append failure stops the execution before another Provider call; metering is fail-closed.
  `repair_no` remains independent of technical `retry_no`.

### Safe observability and data boundary

Events are limited to `ai.provider_attempt_started`, `ai.provider_attempt_succeeded`,
`ai.provider_attempt_failed`, `ai.retry_scheduled`, `ai.fallback_authorized` and
`ai.fallback_denied`, with bounded Provider/model/attempt/status/error metadata.
`provider_attempt_id` is not a metric label. Prompt, input/output, raw response, Provider exception
text, fixture/customer content and credentials are never logged or stored in the Usage Ledger.
Customer content remains prohibited during evaluation.

## Consequences

- Retry storms and unbounded Fallback chains are impossible inside this policy.
- Every attempted paid call has an independent accounting record, including honest unknown-cost
  failures, while persistence replay is idempotent.
- The capability is testable without selecting or calling a real Provider. Runtime promotion,
  Provider ordering and live fallback remain separate decisions.
- Historical complete Ledger rows are backfilled with unique attempt IDs. Downgrade refuses to
  fabricate zero usage when unavailable-accounting rows exist.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-L05 and Job/Usage test cases; synced 2026-09-20.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), Retry, Fallback, Usage/Cost, Logging and DoD; synced 2026-09-20.
- Owner-approved frozen 0069 contract and Provider invocation budget, 2026-09-20.

**Unapproved assumptions:** None
