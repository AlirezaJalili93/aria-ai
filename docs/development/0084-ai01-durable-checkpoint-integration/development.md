# Development Record: 0084 AI-01 Durable Checkpoint Integration

- Increment ID: `0084-ai01-durable-checkpoint-integration`
- Date: 2026-09-30
- Owner: Platform/Worker Engineering
- Related workflow: `AI-01 — Context Structuring`
- [Test report](./test-report.md)

## Scope

Compose the 0083 durable invocation checkpoint with the synthetic, single-attempt AI-01 runtime.
Pin exact Source revisions, persist one validated normalized result with one UsageRecord, recover a
failed Domain commit without another Provider call, and finalize Context/Project/Job/checkpoint in
one PostgreSQL transaction. Do not enable retry, repair, fallback, Hosted execution, real
Providers, customer content or paid calls.

## Source Documents

- Owner-approved frozen `0084 — AI-01 Durable Checkpoint Integration Gate` contract,
  2026-09-30.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — AI-01, Usage and recovery gates; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — validation, Usage, versioning and failure behavior; reread directly from Canonical Drive 2026-09-30.
- [ADR-058](../../adr/ADR-058-context-structuring-job-runtime-foundation.md),
  [ADR-065](../../adr/ADR-065-controlled-provider-timeout-recovery.md),
  [ADR-069](../../adr/ADR-069-durable-ai-invocation-recovery.md) and
  [ADR-070](../../adr/ADR-070-ai01-durable-checkpoint-integration.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8401 | Owner 0084 §1 | Checkpoint mode enforces one attempt and rejects semantic Repair | TC-8401, TC-8406 |
| REQ-8402 | Owner 0084 §2 | Caller-created Attempt ID is persisted before invocation and injected into the Fake Provider | TC-8401, TC-8404 |
| REQ-8403 | Owner 0084 §3/8 | Deterministic fingerprint and exact Source identity/hash revalidation | TC-8402, TC-8405 |
| REQ-8404 | Owner 0084 §4 | Strict `context_structuring_checkpoint_v1` codec excludes rationale and raw Source text | TC-8402, TC-8405 |
| REQ-8405 | Owner 0084 §5 | `result_ready` recovery reuses the same Job, Attempt, payload and Usage | TC-8404 |
| REQ-8406 | Owner 0084 §6 | Context Items, Project Version, Job success and payload cleanup commit atomically | TC-8404 |
| REQ-8407 | Owner 0084 §7 | Invalid checkpoint and unknown outcome remain separate fail-closed codes | TC-8403, TC-8405 |
| REQ-8408 | Owner 0084 Gate | Actual `aria_worker`, RLS isolation, no leakage and migration recovery | TC-8404, TC-8407 |
| REQ-8409 | Owner activation boundary | No Hosted composition, real Provider, customer data or paid call | TC-8406 |

## Assumptions and Clarifications

The owner froze the single-attempt boundary, exact attempt identity, input fingerprint material,
versioned codec, atomic finalization, error separation and activation exclusions. A newer Source
does not invalidate a pinned execution; only pinned identity/integrity mismatch does. Existing raw
Worker SELECT policy is outside this increment.

**Unapproved assumptions:** None

## Changes

- Added ADR-070 and Migration 0032's logical-attempt uniqueness guard.
- Added deterministic AI-01 input fingerprinting and a strict versioned checkpoint codec.
- Added optional checkpoint ownership to the provider-neutral Context Structuring use case while
  preserving legacy Workflow-owned and Coordinator-owned Usage paths.
- Added an Infrastructure runtime that creates the Attempt before Fake invocation, validates
  response identity, atomically checkpoints normalized output/Usage and recovers the same result.
- Extended AI-01's PostgreSQL Unit of Work to finalize and clear the checkpoint in the same
  transaction as Context Items, Project version advancement and Job success.
- Added unit, static-contract and real PostgreSQL crash/recovery/RLS tests under `aria_worker`.

## Structure Preservation

- Application code imports no SQLAlchemy, Celery or Provider SDK.
- Codec and checkpoint ownership are provider-neutral; PostgreSQL and Fake composition remain in
  Worker Infrastructure.
- No new endpoint, Queue event, task, deployable service or Hosted composition was added.
- Existing AI-01 paths remain available and checkpoint mode is opt-in and synthetic-only.
- Queue/Outbox identity-only envelopes are unchanged; content is not added to telemetry.

## Senior Review

- PASS: stable Attempt identity is created before invocation and returned unchanged by the Fake.
- PASS: deterministic ordering removes database query order from the fingerprint.
- PASS: recovery never selects a newer Source or invokes the Provider again.
- PASS: payload cleanup is inside the Domain transaction and rolls back with all business writes.
- PASS: one actual invocation produces one Usage row and one Context Version.
- PASS: Worker cross-Tenant checkpoint access remains denied without broad RLS redesign.
- PASS: Hosted composition remains absent.

## Verification

See [test-report.md](./test-report.md). The isolated PostgreSQL 16 gate passed under the actual
Worker role. Repository-wide results are recorded after the final run.

## Remaining Risks

- Multi-attempt Technical Retry, Semantic Repair and Fallback checkpoint composition are deferred.
- Real Provider, customer-content and Hosted activation remain blocked by separate Data/Security,
  quality and release gates.
- The action-required operational UX/API for ambiguous outcomes remains outside 0084.

**Final status:** PASS
