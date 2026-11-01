# ADR-062: Scope Generation Runtime Foundation

- **Status:** Accepted / Frozen — owner approval received 2026-09-27
- **Date:** 2026-09-27
- **Increment:** 0075 / AI-05 Scope Generation Runtime Foundation
- **Extends:** ADR-041, ADR-042, ADR-043, ADR-057

## Context and authority

K03 currently validates and writes a new Scope Draft through a standalone writer. It does not
finalize a Job in the same transaction and does not reject an empty eligible Requirement set.
Connecting AI-05 to the durable Worker changes that persistence boundary; the owner accepted
this ADR before implementation. The owner's 0075 decision is authoritative for
the nonempty Requirement precondition and the synthetic-only activation boundary.

## Already approved constraints

- One exact `context_version` is required. At least one eligible Context Item and at least one
  eligible Requirement are required. Eligible Requirements belong to the same Account, Project
  and Context Version and have status `draft|confirmed`; `removed|superseded` are excluded.
- Zero eligible Requirements fails **before any AI invocation** with stable code
  `SCOPE_REQUIREMENTS_REQUIRED`. No provider attempt or UsageRecord is created.
- K02 is authoritative for blocking Gaps: an open Critical Gap in the current Context Version
  blocks generation. `resolved|dismissed` Gaps are non-blocking. A Draft already present for the
  same `(project_id, context_version)` causes `SCOPE_DRAFT_ALREADY_EXISTS`, never overwrite.
- Only an explicit internal command, deterministic Fake Provider and synthetic fixtures are in
  scope. No public endpoint, AI-04-to-AI-05 chaining, customer content, paid Provider, runtime
  Primary/Fallback or hosted activation is authorized.
- A validated K01 Scope Draft with its canonical trace lineage and `Job -> succeeded` must
  finalize in **one PostgreSQL transaction**. A failed commit exposes neither a Draft nor a
  succeeded Job. The K01 unique constraint remains the final duplicate-Draft guard.
- Queue-level automatic retry remains disabled. Fake/synthetic re-execution after a persistence
  interruption may be tested; ambiguous post-response **paid** invocation recovery remains
  separately blocked.

## Frozen 0075 runtime contract

### Durable command and delivery identity

- Schedule only through an explicit internal Application command bound to `account_id`,
  `project_id`, `context_version` and one logical `job_id`.
- `job_type=scope_generation`, Outbox `event_type=scope.generation_requested.v1`,
  `delivery_channel=job_queue` and Celery task `aria.scope.generate.v1`.
- The Queue envelope is exactly `message_version`, `outbox_event_id`, `job_id`. The Worker
  resolves Project, pinned input, tenant authority and execution configuration from PostgreSQL.
  Scope/Context/Requirement/Gap text, prompts and customer payload never enter Outbox or Queue.
- Job and Outbox insert commit together. A new command is not scheduled if a Draft already exists
  or a `queued|running` Scope Generation Job exists for the same Account, Project and Context
  Version. A partial unique PostgreSQL index is the final active-Job race guard.

### Preflight and exact input

- Before scheduling, tenant-scope the Project and pin its exact Context Version. Resolve eligible
  Context Items and Requirements and the K02 Gap decision from that version; reject an empty
  eligible set or nonempty canonical blocking set before the Fake Provider can run.
- Persist the exact sorted input revision identities with the Job and verify them again before
  finalization. This prevents the Worker from silently choosing a later Context/Requirement/Gap
  state. Input revision metadata remains in PostgreSQL, not in the Queue envelope.
- A mismatch between pinned and current eligible input fails closed with stable
  `SCOPE_GENERATION_INPUT_CHANGED`, `retryable=false`. It does not silently select latest state,
  regenerate or overwrite a Draft; no Draft or Job success is committed. A new explicit command
  is required for changed input. This is not a technical Provider retry or fallback condition.

### Execution and finalization boundary

- Reuse the provider-neutral K03 validation, bounded repair, K01 `scope_content_schema_v1`
  structure, K02 readiness and Usage Ledger semantics. `Pages` and `Sections` remain structurally
  mapped to the one canonical `pages_sections` section. No thirteenth section is introduced.
- Replace the standalone K03 `ScopeDraftWriter.create_ai_draft()` final write with an
  Application-facing finalization port whose PostgreSQL implementation atomically checks the
  pinned snapshot and Draft absence, inserts the validated Draft with K01 trace lineage, and
  transitions the same Job to `succeeded`. This is a boundary change, not a second Scope Draft
  source of truth. The existing K01 Draft and Job tables remain authoritative.
- Duplicate delivery of a completed Job is a no-op. Concurrent delivery uses the existing
  JobExecutionGuard and database uniqueness; neither duplicate Drafts nor duplicate committed
  business effects are allowed. If final commit fails, the Draft insert and Job success roll back
  together and the same logical Job remains recoverable for controlled synthetic execution.
- No automatic regeneration, implicit Scope overwrite, public result snapshot, new Scope table
  or Scope readiness column is added. Immutable Scope Version creation remains K05's separate
  concern.

## Security, observability and activation

Worker database authority must be the minimum needed for tenant-scoped snapshot reads, Draft
insert and Job finalization. RLS remains enabled; API, `anon` and `authenticated` roles receive no
new direct Draft-write privilege. Migration upgrade/downgrade and grants require PostgreSQL tests.
The short finalization transaction uses a fixed SECURITY DEFINER lock helper for Context Item,
Requirement and Gap tables; this avoids granting the Worker broad data-update privilege solely
to protect the pin recheck against concurrent writes. The helper exposes no row data and is
executable only by `aria_worker`.

Safe events may include bounded Account/Project/Job/Draft IDs, Context Version, workflow/schema
versions, counts, outcome, duration and reason code. Scope content, trace arrays, Context,
Requirement or Gap text, prompt, raw Provider output and Queue payload are prohibited in logs.
Identifiers such as `job_id` are correlation fields, not metric labels.

The 0075 gate must prove pre-AI `SCOPE_REQUIREMENTS_REQUIRED` (zero invocation and UsageRecord),
K02 blocking, exact revision pinning, existing-Draft conflict, concurrent scheduling, atomic
Job/Outbox creation, atomic Draft/Job finalization, duplicate delivery, commit-failure recovery,
least-privilege/RLS, and zero customer-content or real-Provider invocation. Passing Fake Provider
tests proves orchestration only, not model quality or hosted readiness.

## Accepted decision

The owner approved the durable identifiers, active-Job uniqueness, exact pin/recheck policy and
finalization-port design on 2026-09-27. Contract-first 0075 implementation, its migration and
controlled synthetic Worker runtime are authorized. Public Endpoint, customer content, paid
Provider, Primary/Fallback runtime, AI-04-to-AI-05 chaining and hosted activation remain
unauthorized. This approval does not authorize commit or push.

## Sources and traceability

| Requirement | Source | Implementation boundary | Required verification |
| --- | --- | --- | --- |
| REQ-0075-01 | Owner's 0075 decision, 2026-09-27; AI-05 Workflow | Internal command preflight | Empty eligible Requirement set rejects before AI/Usage |
| REQ-0075-02 | ADR-042 / K02; reaffirmed for 0075 | K02 readiness input | Open Critical blocks; dismissed/resolved do not |
| REQ-0075-03 | Owner's 0075 decision; ADR-041/043 | Draft+Job finalization port | Commit rollback exposes neither Draft nor success |
| REQ-0075-04 | Owner's 0075 decision; ADR-057/060/061 | Job/Outbox/Worker boundary | Synthetic-only, no public or hosted activation |

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K03; reread 2026-09-27.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-05; reread 2026-09-27.
- [ADR-041](ADR-041-scope-draft-model.md), [ADR-042](ADR-042-scope-readiness-policy.md),
  [ADR-043](ADR-043-scope-generation-use-case.md), [ADR-057](ADR-057-durable-outbox-delivery-runtime.md),
  [ADR-060](ADR-060-requirement-generation-runtime-foundation.md),
  [ADR-061](ADR-061-gap-detection-runtime-foundation.md).
- Owner's explicit 0075 contract direction dated 2026-09-27.
- Owner's ADR-062 approval and `SCOPE_GENERATION_INPUT_CHANGED` clarification dated 2026-09-27.
