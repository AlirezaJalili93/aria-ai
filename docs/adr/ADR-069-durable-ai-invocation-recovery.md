# ADR-069 — Durable AI Invocation Recovery Boundary

- Status: Accepted
- Date: 2026-09-30
- Decision owner: Product and Engineering
- Extends: ADR-056, ADR-058, ADR-061, ADR-062 and ADR-065

## Context

The bounded Provider policy meters actual invocations and the synthetic Job runtimes recover
database finalization failures by executing the Fake Provider again. That behavior is not safe for
a real or paid Provider: after a response is received, a Worker can fail before the normalized
result and domain writes become durable. Re-invoking in that ambiguous window can duplicate cost
and produce a different semantic result. The canonical AI Workflow requires complete Usage,
observable failure and deliberate raw-response retention; it does not authorize an exactly-once
Provider assumption.

## Decision

### Durable attempt and checkpoint lifecycle

One operational checkpoint is identified by the same stable `provider_attempt_id` used by the
Usage Ledger. Its states are:

```text
started → result_ready → finalized
       ↘ outcome_unknown
```

Before a Provider call, the Worker persists `started` with exact Tenant, Project, Job, workflow,
prompt, output-schema, Provider/model/price, retry/repair and input-fingerprint identity. A
successful Provider result must be normalized and schema-valid before persistence. The normalized
result, its canonical SHA-256 hash and the one complete UsageRecord then commit in one PostgreSQL
transaction.

Raw prompts, raw Provider responses, credentials and Queue/Outbox payload copies are prohibited.
The normalized result is transient customer-derived content: it is Tenant-scoped, protected by
RLS, available only to the Worker path and never written to logs or metric labels.

### Recovery semantics

- `result_ready`: reuse the durable normalized result. No Provider re-invocation, new attempt ID or
  new UsageRecord is permitted. Retry only deterministic validation/domain finalization.
- `finalized`: the domain outcome is already durable; recovery is an idempotent no-op.
- `started` without a durable result: Provider invocation may have occurred. Transition to
  `outcome_unknown`, fail the existing Job with stable reason
  `AI_INVOCATION_OUTCOME_UNKNOWN`, `retryable=false`, and require manual/action-required handling.
- `outcome_unknown`: remain terminal for automatic execution. No assumption of zero Usage or cost
  is made and no automatic Provider re-invocation is allowed.

`failed_action_required` is a semantic UX classification only. The Sprint 1 Job state machine is
unchanged; the persisted Job uses existing status `failed` plus the stable reason code.

### Finalization and cleanup

Domain finalization remains workflow-owned. It must consume the exact checkpoint identity and
result. After the Job/domain transaction succeeds, cleanup changes the checkpoint to `finalized`,
clears `normalized_result`, and retains only non-content identity, timing and result hash. Cleanup
is idempotent and requires the same Job to be `succeeded`; a cleanup interruption cannot authorize
Provider re-invocation and is retried as storage hygiene only.

### Security and activation boundary

The table has restrictive Account/Project/Job foreign keys, forced RLS, per-transaction Account
scope and no API/Data API authority. `aria_worker` receives only SELECT/INSERT/UPDATE required by
the fixed adapter; DELETE is denied. Identity is immutable and database checks permit only the
frozen state transitions.

0083 implements and tests this boundary using synthetic data. It is not composed into Hosted
Worker runtime. Real Providers, customer content, paid calls and Hosted activation remain NO-GO
until separate Data/Security and release gates pass.

## Consequences

- `1 actual Provider invocation = 1 provider_attempt_id = 1 UsageRecord` remains enforceable.
- A durable response can survive domain persistence failure without a second paid call.
- The irreducible pre-checkpoint ambiguity fails closed instead of claiming exactly-once delivery.
- The transient normalized payload introduces a deliberate operational store, not a second domain
  source of truth; successful domain finalization removes that payload.
- Existing synthetic runtimes are unchanged until a later workflow-specific composition increment
  proves their codecs and finalization wiring.

## Required evidence

- Successful normalized result and UsageRecord commit atomically.
- Recovery reuses one checkpoint and preserves exactly one UsageRecord.
- An ambiguous started Attempt fails the same Job with the stable reason and creates no fabricated
  zero-cost UsageRecord.
- Cleanup removes content while retaining the hash and is impossible before Job success.
- Cross-Tenant access, DELETE, invalid transition and identity mutation fail.
- Logs, metrics, Queue and Outbox contain no normalized result, prompt or raw response.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), async recovery, Usage and release gates; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), §§3, 6, 19–22, 27–33; reread directly from Canonical Drive 2026-09-30.
- Owner-approved frozen `0083 — Durable AI Invocation Recovery Boundary` contract, 2026-09-30.

**Unapproved assumptions:** None
