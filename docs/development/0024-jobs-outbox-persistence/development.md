# Development Record: 0024 Jobs and Outbox Persistence

- Increment ID: `0024-jobs-outbox-persistence`
- Date: 2026-09-02
- Owner: Codex (implementation and senior review)
- Related plan/issue: `S1-E01 — Jobs Table/State Machine`; persistence slice of `S1-E03 — Transactional Outbox`; logical migration `M008`
- [Test report](./test-report.md)

## Scope

Implement the documented Job state vocabulary, current Jobs/Outbox persistence schema, Domain and
Application ports, an atomic Job-plus-Outbox scheduling Unit of Work, tenant consistency, immutable
Outbox payload, safe logging and migration security. Queue transport, relay retry/backoff,
dead-letter behavior, Worker consumption and Job Status API are explicit non-goals owned by later
approved stories.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-E01 and S1-E03; read 2026-09-02.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — current Jobs/Outbox fields, states and indexes; read 2026-09-02.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — logical M008, transaction rule and migration tests; read 2026-09-02.
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — PostgreSQL Job/Outbox baseline and payload immutability; read 2026-09-02.
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — modular-monolith Jobs boundary, Source of Truth and async state machine; read 2026-09-02.
- Repository governance, `AGENTS.md`, ADR-002, ADR-008 and [ADR-013](../../adr/ADR-013-jobs-outbox-persistence.md).
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [database migrations](https://supabase.com/docs/guides/deployment/database-migrations), and [Queues](https://supabase.com/docs/guides/queues) — current platform guidance checked 2026-09-02; no relevant schema blocker found.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-126 | S1-E01; Data Dictionary | Current `jobs` fields and five-state vocabulary | TC-2401, TC-2404 |
| REQ-127 | System Architecture | `queued -> running -> terminal` Domain transition policy | TC-2402 |
| REQ-128 | Data Dictionary; Architecture | User Project Jobs are Account-anchored and cross-tenant Project linkage is rejected | TC-2401, TC-2405 |
| REQ-129 | S1-E03; ADR-002 | Job and Outbox Event are persisted before one Application-owned commit | TC-2403, TC-2406 |
| REQ-130 | Production Data Architecture | Outbox payload is immutable after commit | TC-2406 |
| REQ-131 | Data Dictionary; Migration Plan; Supabase | Queue/tenant indexes, RLS, fail-closed grants and safe downgrade/re-upgrade | TC-2404, TC-2407 |
| REQ-132 | Logging baseline | Safe Job outcome/failure events omit payload and idempotency key | TC-2403 |
| REQ-133 | S1-E02/E04 scope; ADR-013 | No queue provider, retry duration, relay or consumer behavior is invented | TC-2408 |
| REQ-134 | Repository governance | Linked records, full quality gates and senior review | TC-2409 |

## Assumptions and Clarifications

The updated Detailed Data Dictionary is the current semantic schema authority. ADR-013 explicitly
supersedes the older `task_type`, `attempt_no`, `input_ref/output_ref` and `completed_at` names.
Transport and retry policy remain deferred because the approved documents do not define them.

**Unapproved assumptions:** None

## Changes

- Added framework-independent Job and Outbox entities, exact status vocabularies, attempt invariants,
  Project tenant anchoring and the documented one-way Job transition policy.
- Added Application ports and `ScheduleJobUseCase`, which persists Job and Outbox rows through one
  Unit of Work and emits safe `job.queued` / `job.schedule_failed` operational events.
- Added SQLAlchemy models/repositories and logical M008 (`0005_jobs_outbox`) with current Dictionary
  names, tenant/project FKs, named checks, indexes, RLS, fail-closed Data API grants and safe recovery.
- Added a database trigger that prevents committed Outbox payload mutation while allowing lifecycle
  columns to be updated by the future relay.
- Updated migration/data-model mirrors, registered Jobs metadata and added ADR-013 plus contract,
  Domain, Application and PostgreSQL tests.

## Architecture and Design Decisions

See [ADR-013](../../adr/ADR-013-jobs-outbox-persistence.md). The module remains inside the accepted
modular monolith. PostgreSQL is the Source of Truth; a queue adapter is not selected in this slice.

## Structure Preservation

- Dependency direction remains `jobs/domain -> jobs/application -> jobs/infrastructure`; Domain has
  no framework, database, queue or observability imports.
- The existing API, Worker and Context modules are not moved or rewritten. No deployable is added.
- Existing Alembic revisions remain immutable; `0005_jobs_outbox` is an additive head revision.
- Logical M004-M007 are not silently implemented; physical revision ordering is recorded separately
  from the product migration map.

## Senior Review

- **Architecture:** PASS. Domain has no framework dependency; Application owns transaction
  orchestration; SQLAlchemy and PostgreSQL details remain in Infrastructure.
- **Data integrity:** PASS. Named status/attempt checks, composite Project tenant FK and the Outbox
  payload trigger are enforced by PostgreSQL rather than only Application code.
- **Transaction safety:** PASS. Real PostgreSQL tests prove Job and Event commit together and a
  failing Event write rolls the Job back.
- **Security/privacy:** PASS. RLS and fail-closed Data API grants are preserved; logs contain trace,
  tenant, Project, Job, duration and outcome but no payload or idempotency key.
- **Scope control:** PASS. Review confirmed no queue client, relay timing, retry duration,
  dead-letter, consumer or public API behavior entered this persistence slice.
- Review corrections included explicit Project/Account consistency, payload immutability at the DB
  boundary and a real rollback assertion rather than testing only the success transaction.

## Verification

PASS — unit, contract, real PostgreSQL, migration SQL, lint, typecheck and production build results
are recorded in the linked report. The final repository quality/architecture seal is included there.

## Remaining Risks

- S1-E03 relay recovery and duplicate delivery behavior depend on the still-unapproved E02/E04
  transport/retry contracts and are not claimed complete by this persistence slice.
- S1-D02 will be the first business operation that atomically creates Source, Version, Job and
  Outbox Event; its public request shape and idempotency retention still require an exact contract.
