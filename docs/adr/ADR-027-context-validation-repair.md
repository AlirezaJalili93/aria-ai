# ADR-027: Bounded Context Validation Repair

- **Status:** Accepted
- **Date:** 2026-09-06
- **Story:** S1-H03 — Repair Strategy
- **Amends:** ADR-024 and ADR-026

## Context

The approved AI Workflow requires bounded semantic Repair after structured-output validation,
separate usage metering for each Repair execution and explicit failure after the permitted limit.
It does not define a numeric limit or distinguish semantic Repair attempts from technical Provider
retries. The owner resolved these H03 boundaries on 2026-09-06.

## Decision

- Sprint 1 uses an explicit, versioned `ContextRepairPolicy`. `max_repairs=1` is the canonical
  active policy and `max_repairs=0` explicitly disables Repair. The Application has no hidden
  default and accepts no larger Sprint 1 value.
- With `max_repairs=0`, initial validation failure preserves the original structured validation
  error. `CONTEXT_REPAIR_EXHAUSTED` is emitted only after at least one approved Repair attempt is
  consumed; it is non-retryable.
- Repair uses the same provider-neutral `AIExecutionPort`, workflow version, output schema,
  routing policy, cost budget and timeout policy. It uses an explicit `repair_prompt_version`.
  Repair does not introduce Provider selection, fallback or tier escalation.
- Technical Provider retries remain owned by the existing execution policy. `retry_no` counts
  retries inside one Provider execution; `repair_no` counts a new semantic execution. A Provider
  retry during Repair changes `retry_no` but retains the current `repair_no`.
- Repairable reasons are the bounded vocabulary `schema_invalid`, `invalid_source_reference`,
  `unsupported_claim` and `duplicate_candidate`. A Source Reference is Repairable only when its
  defect was produced by the model against the immutable snapshot. Provider, repository/database,
  mutable Source-state and `insufficient_context` failures do not trigger Repair.
- Repair input contains the immutable initial Source snapshot, rejected output, current
  `repair_no`, bounded validation reason, versions/policy and original execution identifiers. The
  rejected output is ephemeral in-memory AI input: it is never written to a log, error detail,
  Usage record, Job/Outbox payload, analytics event or trace attribute.
- Every repaired output re-enters the complete H02 schema, Source/provenance, unsupported-claim,
  duplicate and whole-Batch validation pipeline. A successful Batch uses the existing single
  Context write transaction. Initial rejection, failed Repair and exhaustion cause no Context
  write and no Context Version increment.
- Every returned AI invocation creates an independent append-only Usage record. Migration 0009
  adds `repair_no SMALLINT NOT NULL DEFAULT 0 CHECK (repair_no >= 0)`: original execution is `0`,
  first semantic Repair is `1`, and `N` means the Nth semantic Repair. The database intentionally
  has no `repair_no <= 1` constraint because the Sprint limit is policy, not a permanent data
  invariant.
- Safe lifecycle events are `context.repair_started`, `context.repair_succeeded`,
  `context.repair_failed` and `context.repair_exhausted`. Their reason is one of the bounded
  Repairable codes; raw/canonical Source text, candidate content, rejected output, prompt,
  validation detail, Source URL/storage reference, credentials and PII are forbidden.

## Consequences

The Context workflow can recover once from deterministic model-output defects without creating an
unbounded cost loop or bypassing H02 validation. Usage can distinguish first-pass cost, semantic
Repair cost and technical Provider retry cost. Exhaustion is deterministic and cannot partially
advance operational Context state.

## Deferred

- Any policy allowing more than one semantic Repair.
- Repair-specific Provider, routing Tier, fallback or escalation behavior.
- Storage or encrypted Artifact references for rejected output.
- Public trigger, concrete Job/Queue composition and end-user Failure UX integration.
- Aggregate KPI queries/dashboards over Repair Usage; H03 only records authoritative inputs.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H03
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — validation, Repair, retry and Usage
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit)
- Owner clarification dated 2026-09-06
