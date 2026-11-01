# ADR-026: Provider-Neutral Context Structuring Workflow

- **Status:** Accepted
- **Date:** 2026-09-06
- **Story:** S1-H02 — Context Structuring Workflow
- **Supersedes for H02:** implicit semantic duplicate detection and normalize/merge behavior

## Context

The backlog defines `canonical input → context builder → model → schema validation → business
validation → unsupported claim check → persist`, and prohibits invalid AI output from entering the
database. The AI workflow additionally requires provenance, structured output, usage metering and
provider neutrality. The owner resolved the remaining H02 execution boundaries on 2026-09-06,
including the exact-duplicate behavior.

## Decision

- `ContextStructuringUseCase` is a shared, framework-neutral Backend Application service. The
  Worker invokes it through a thin task wrapper and does not own a second Context Domain or copy
  validation/persistence rules.
- H02 calls the existing provider-neutral `AIExecutionPort`. Tests use a deterministic Fake
  Adapter; no Provider SDK, model name or concrete Provider runtime is introduced.
- At the start of one execution, the Source snapshot is resolved exactly once. It contains the
  latest ready Version (`MAX(version_no)`) for every non-deleted Source in the Account/Project.
  Sources or Versions becoming ready after this read are not part of that execution.
- AI candidates remain untrusted. The complete Batch passes schema, business, provenance,
  Source Reference bounds and unsupported-claim validation before any Context Item write.
- Every Fact candidate requires at least one valid Source Reference to the immutable execution
  snapshot. Any invalid item or unsupported claim rejects the complete Batch and persists nothing.
- Duplicate identity is exact `(item_type, content)` equality inside one Batch. An exact duplicate
  rejects the complete Batch with stable error `DUPLICATE_CONTEXT_ITEM`. Non-exact content is not
  treated as a duplicate. Normalization, fuzzy/semantic similarity, merge, silent deduplication,
  Source Reference combination and confidence resolution are deferred.
- `rationale_short` may exist only on the in-memory candidate. It is never persisted, logged or
  emitted to analytics.
- After validation, one database transaction locks the Project, allocates
  `current_context_version + 1`, writes the complete Batch as proposed AI Context Items and advances
  the Project pointer. Failure rolls back every write and consumes no Version number.
- The authoritative Usage Ledger records the provider-neutral execution outcome before candidate
  persistence. The caller supplies already-approved workflow, prompt, pricing, routing, budget and
  timeout policy values; H02 invents none of them.
- Structured lifecycle events are `context.structuring_started`,
  `context.structuring_completed` and `context.structuring_failed`. They contain safe identifiers,
  Version/duration/status/reason metadata only, never Context content, canonical text, raw Source
  References or rationale.

## Consequences

One successful execution creates one auditable, gap-free integer Context Version. Validation and
persistence are deterministic and all-or-nothing, while Source input is reproducible even when the
project changes during the external AI call. A concrete unsupported-claim implementation and real
Provider remain external adapters to this use case.

## Deferred

- Public endpoint and its entitlement, quota and idempotency integration; the API contract exists
  but integration is outside H02.
- Concrete Job type and message envelope.
- Queue transport, scheduling and runtime composition.
- Repair behavior is defined by ADR-027; Provider retry, fallback and escalation remain deferred.
- Provider adapter/runtime (G02/G03) and any Provider or model selection.
- Semantic duplicate normalization/merge policy.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H02
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-01
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit)
- [Repository & Code Structure Specification v1.0](https://docs.google.com/document/d/1NkMTAZRTIgyqfd1C4pKVRRK69swPQI7T-YymV9hBzz0/edit)
- Owner clarification dated 2026-09-06
