# Development Record: 0071 Context Structuring Job Runtime Foundation

- Increment ID: `0071-context-structuring-job-runtime-foundation`
- Date: 2026-09-21
- Owner: Platform/Worker Engineering
- Related story: `S1-E03 — Context Structuring Job Runtime Foundation`
- [Test report](./test-report.md)

## Scope

Implement an explicit, durable and synthetic-only runtime foundation for AI-01 Context Structuring.
Provide an internal idempotent scheduler, exact Job/Outbox identities, minimal Queue delivery,
atomic Context/Project/Job finalization and recoverable Fake-Provider commit failure. Do not expose
the future public endpoint, compose the task in Hosted Worker, select a runtime Provider, process
customer content or permit paid calls.

## Source Documents

- Owner-approved and frozen `0071 — Context Structuring Job Runtime Foundation` contract,
  2026-09-21.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), AI-01, Job/Outbox and Worker sequencing; synced 2026-09-21.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), provider-neutral AI-01 and validation boundaries; synced 2026-09-21.
- [Final Production Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit), PostgreSQL authority, Worker and Outbox boundaries; synced 2026-09-21.
- [Test Strategy v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit), async recovery and failure verification; synced 2026-09-21.
- [ADR-016](../../adr/ADR-016-outbox-relay-contract.md),
  [ADR-017](../../adr/ADR-017-worker-idempotency-foundation.md),
  [ADR-026](../../adr/ADR-026-context-structuring-workflow.md),
  [ADR-027](../../adr/ADR-027-context-validation-repair.md),
  [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md) and
  [ADR-058](../../adr/ADR-058-context-structuring-job-runtime-foundation.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-7101 | Explicit AI-01 trigger | Internal `ScheduleContextStructuringUseCase`; no Parser chaining or router composition | TC-7101, TC-7111 |
| REQ-7102 | Idempotent command | Required non-empty key, Project-aware hash, exact 202 replay with relative status URL | TC-7101, TC-7102 |
| REQ-7103 | One active Job per Project | Partial unique PostgreSQL index for `queued|running` AI-01 Jobs | TC-7103 |
| REQ-7104 | Frozen delivery identity | Exact event/channel/task and identifier-only versioned Queue envelope | TC-7104 |
| REQ-7105 | Duplicate suppression | Provider-neutral advisory `JobExecutionGuard`; completed delivery is a no-op | TC-7105, TC-7109 |
| REQ-7106 | PostgreSQL-resolved Context | Worker resolves Job/Outbox and latest ready Source Versions within Tenant/Project | TC-7106 |
| REQ-7107 | Atomic success | Context Items, Project Context Version and Job success in one transaction | TC-7107 |
| REQ-7108 | Fake-only commit recovery | Rollback leaves same running Job recoverable; synthetic re-execution creates one Version | TC-7108 |
| REQ-7109 | Synthetic-only Provider | Deterministic Fake, zero usage/cost, no runtime composition or paid Provider | TC-7106, TC-7111 |
| REQ-7110 | Least privilege | Project SELECT + column-only Version UPDATE; AI Context INSERT policy | TC-7110 |
| REQ-7111 | Safe observability | Identifiers/reason codes only; Context, prompts, payload and generated content excluded | TC-7111 |
| REQ-7112 | Activation exclusions | Public Endpoint and Hosted task/Fake composition remain absent | TC-7111 |

## Assumptions and Clarifications

The owner froze all 0071 runtime identities, command semantics, active-Job rule, transaction
boundary, synthetic recovery allowance and activation exclusions. Real/paid post-response recovery
is explicitly deferred and was not inferred from the Fake Provider behavior.

**Unapproved assumptions:** None

## Changes

- Added Migration 0026 with the active-AI-01 partial unique index and narrow Worker authority.
- Added an internal Application scheduler and SQLAlchemy Unit of Work for exact idempotent
  Job/Outbox creation; no API router composes it.
- Added the AI-01 Worker consumer, exact message parser, Celery task registration function,
  PostgreSQL Job/snapshot/finalization adapters and deterministic synthetic adapter.
- Extended the existing Outbox publisher with the approved event/task mapping while preserving
  the identifier-only Queue envelope and disabled SDK retry.
- Extended the shared Context Structuring transaction to finalize its Job in the same Unit of Work
  as Context Items and Project Context Version.
- Generalized the PostgreSQL execution guard exceptions so the shared Worker boundary no longer
  depends on TXT Parser-specific Application errors.
- Added unit, static contract and real PostgreSQL concurrency/atomic recovery tests.
- Added ADR-058 and updated Worker, migration, architecture and data-model mirrors.

## Architecture and Design Decisions

- PostgreSQL is authoritative for command identity, Tenant/Project context, Source snapshots, Job
  state and business writes. Queue messages carry identifiers only.
- The future endpoint contract is preserved internally as `job_id + status_url`, but no route is
  registered in 0071.
- The synthetic adapter returns deterministic provenance-aware candidates without echoing input.
  It is not a hosted runtime default and is never promoted by this increment.
- Queue redelivery retry and AI technical retry are separate concerns. The task declares no
  automatic Queue retry.
- Finalization uses one Unit of Work. A failed commit cannot expose Context Items, a new Project
  version or a succeeded Job independently.

## Structure Preservation

- No new deployable, public API, UI route, Queue, runtime Provider or Hosted process was added.
- Shared Application code imports no Celery, SQLAlchemy or Provider SDK.
- Celery and SQLAlchemy remain in Worker Infrastructure; API Application depends on ports.
- Existing modular-monolith API/Worker/package boundaries and the current Worker composition root
  are preserved.
- Canonical repository mirrors retain source links and the 2026-09-21 synchronization date.

## Senior Review

- PASS: corrected the internal result from non-contractual `status` to exact relative `status_url`.
- PASS: replaced Parser-specific execution-guard errors with provider-neutral port errors.
- PASS: narrowed Project UPDATE authority from table-wide access to
  `current_context_version` only; upgrade first revokes any earlier broad development grant.
- PASS: concurrent schedulers are stopped by PostgreSQL, not check-then-insert logic.
- PASS: Queue and Outbox payloads contain no Project ID, Context, prompt or customer payload.
- PASS: Context writes, Project version advancement and Job success are ordered before one commit.
- PASS: simulated commit failure rolls back all domain writes and recovery reuses the same Job.
- PASS: Fake adapter and task registration are absent from API/Worker composition roots.
- PASS: logs exclude the synthetic sensitive marker and all content-bearing fields.

## Verification

See [test-report.md](./test-report.md). Focused unit and PostgreSQL integration evidence is
recorded there. The clean Migration chain, component regressions and repository-wide quality gates
all passed.

## Remaining Risks

- Real/paid Provider success followed by ambiguous persistence failure has no approved recovery
  policy; Provider promotion and customer-content activation remain blocked.
- Public authorization/error mapping, entitlement/quota and endpoint composition require a later
  approved increment.
- Hosted Worker task registration and activation remain disabled.

**Final status:** PASS
