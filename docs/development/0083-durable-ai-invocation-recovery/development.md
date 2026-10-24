# Development Record: 0083 Durable AI Invocation Recovery

- Increment ID: `0083-durable-ai-invocation-recovery`
- Date: 2026-09-30
- Owner: Platform/Worker Engineering
- Related gate: Post-Provider persistence recovery boundary
- [Test report](./test-report.md)

## Scope

Implement the approved provider-neutral and synthetic-only recovery foundation for the ambiguous
window between an actual Provider invocation and Domain finalization. Persist a durable Attempt,
atomically checkpoint one normalized result with its one UsageRecord, reuse that result without a
second invocation, fail an uncheckpointed started Attempt with a stable action-required reason and
clean transient content only after Job success. Do not compose this capability into Hosted Worker,
select/promote a Provider, process customer content or authorize paid calls.

## Source Documents

- Owner-approved frozen `0083 — Durable AI Invocation Recovery Boundary` contract, 2026-09-30.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — async recovery, Usage and release gates; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — execution, validation, Usage, retention and failure behavior; reread directly from Canonical Drive 2026-09-30.
- [ADR-056](../../adr/ADR-056-ai-failure-policy.md),
  [ADR-058](../../adr/ADR-058-context-structuring-job-runtime-foundation.md),
  [ADR-065](../../adr/ADR-065-controlled-provider-timeout-recovery.md) and
  [ADR-069](../../adr/ADR-069-durable-ai-invocation-recovery.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8301 | Owner 0083; ADR-069 | `AIInvocationAttempt`, durable `started` checkpoint | TC-8301, TC-8305 |
| REQ-8302 | Owner Usage invariant; ADR-056/069 | Atomic normalized result + Usage write keyed by one `provider_attempt_id` | TC-8302, TC-8303 |
| REQ-8303 | Owner recovery rule; ADR-069 | Hash-verified `reuse_result` decision without new Usage or invocation | TC-8302 |
| REQ-8304 | Owner ambiguous rule; ADR-069 | `outcome_unknown` + existing Job `failed/AI_INVOCATION_OUTCOME_UNKNOWN` | TC-8304 |
| REQ-8305 | Owner cleanup rule; ADR-069 | Job-success-gated payload cleanup retaining result hash | TC-8302 |
| REQ-8306 | Owner data boundary; AI Workflow §§29–30 | Forced RLS, scoped setting, no DELETE, no raw prompt/response/logging | TC-8305, TC-8306 |
| REQ-8307 | Migration Plan and repository quality gates | Fresh upgrade, data-safe downgrade refusal, clean downgrade/re-upgrade | TC-8307 |
| REQ-8308 | Owner activation exclusions | No Hosted composition, Provider promotion or customer-content path | TC-8306 |

## Assumptions and Clarifications

The owner explicitly approved an operational normalized-result checkpoint, existing Job `failed`
status with semantic action-required classification, stable unknown-outcome code, state-based
payload cleanup and continued NO-GO for real Provider/customer/Hosted activation. Runtime
composition into AI-01/02/03/05 remains a later workflow-specific increment and is not implied by
this foundation.

**Unapproved assumptions:** None

## Changes

- Added ADR-069 and repository architecture/data/migration mirrors.
- Added Migration 0031 with a Tenant/Project/Job-bound checkpoint table, immutable identity,
  constrained lifecycle, forced RLS, fail-closed public/API grants and Worker least privilege.
- Added the provider-neutral recovery Application contract, canonical normalized-result hashing,
  Usage identity validation and fail-closed recovery decisions.
- Added a PostgreSQL adapter that atomically persists the successful Usage/checkpoint pair, marks
  ambiguous executions and cleans payload only after Job success.
- Added deterministic unit, contract and real PostgreSQL crash/recovery/migration tests.
- Added an isolated Docker PostgreSQL runner and repository command for the controlled gate.

## Structure Preservation

- Domain/Application code imports no SQLAlchemy, Provider SDK or Worker framework.
- PostgreSQL/RLS and Usage-table details remain in Worker Infrastructure and Alembic.
- Existing Job status vocabulary, Usage Ledger, Provider retry budget and workflow finalizers are
  not replaced or weakened.
- No public endpoint, Queue message, Outbox event, deployable service or Hosted composition is
  added.
- The checkpoint is operational and transient; workflow Domain tables remain authoritative.
- Raw prompt/response and normalized content are absent from logs, metrics, Queue and Outbox.

## Senior Review

- PASS: checkpoint success and Usage share one database transaction.
- PASS: durable result recovery reuses identity and cannot append a second Usage record.
- PASS: an uncheckpointed started Attempt fails closed instead of fabricating zero cost.
- PASS: cleanup requires Job success, clears payload and retains its canonical hash.
- PASS: database transition trigger prevents identity mutation and transition skipping.
- PASS: Worker has no DELETE and public/API roles receive no access.
- PASS: Hosted composition does not import or instantiate the new adapter.

## Verification

See [test-report.md](./test-report.md). Final repository-wide results are recorded only after the
last gate run.

## Remaining Risks

- Workflow-specific codecs and atomic Domain-finalization integration are not composed in 0083.
- A real Provider, customer-derived input and paid invocation remain blocked by separate
  Data/Security, evaluation and activation gates.
- `outcome_unknown` intentionally requires an operational/manual action path; no public recovery
  UI or API is introduced here.

**Final status:** PASS
