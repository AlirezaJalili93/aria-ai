# Development Record: 0073 — Requirement Generation Runtime Foundation

- **Status:** COMPLETE
- **Increment:** S1-I02 runtime foundation
- **Source sync date:** 2026-09-22
- [Test report](./test-report.md)

## Scope

Add the approved synthetic-only, internal AI-02 Job/Outbox/Worker runtime without exposing a public
endpoint, chaining AI-01, registering a hosted task, using customer content or invoking a paid
provider.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I02
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-02
- [ADR-031](../../adr/ADR-031-requirement-generation-contract.md)
- [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md)
- [ADR-060](../../adr/ADR-060-requirement-generation-runtime-foundation.md)
- Owner-approved 0073 contract dated 2026-09-22.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-7301 | 0073 contract | Internal synthetic-only Job/Outbox scheduler; no HTTP route | TC-7301, TC-7308 |
| REQ-7302 | 0073 contract | Exact Context version and revision vector persisted on Job | TC-7301, TC-7304 |
| REQ-7303 | 0073 contract; ADR-057 | Identifier-only Outbox/Queue envelope and AI-02 task identity | TC-7302, TC-7303 |
| REQ-7304 | 0073 contract; ADR-031 | Fake Provider Worker executes exact snapshot and validates provenance | TC-7304 |
| REQ-7305 | 0073 contract | Requirement/conflict/Job success atomic finalization | TC-7305 |
| REQ-7306 | 0073 contract | Duplicate suppression, replay safety and recoverable commit failure | TC-7305, TC-7306 |
| REQ-7307 | 0073 safety boundary | No hosted registration, real provider, customer data or automatic retry | TC-7307, TC-7308 |
| REQ-7308 | Repository quality gate | Development record, test report, Senior review and full validation | TC-7309 |

## Assumptions and Clarifications

- **Unapproved assumptions:** None

## Changes

- Added a fail-closed internal scheduler that accepts only explicitly allowlisted synthetic
  Projects, captures the exact Context Version/revision vector and atomically creates the canonical
  `requirement_generation` Job plus `requirement.generation_requested.v1` Outbox event.
- Added the identifier-only `aria.requirements.generate.v1` Celery mapping and controlled task
  registration function with `autoretry_for=()`. Hosted Worker composition deliberately does not
  register it.
- Added an AI-02 Consumer using the existing PostgreSQL advisory `JobExecutionGuard`, strict
  Job/Outbox validation and same-Job recovery after persistence interruption.
- Added a deterministic synthetic AI adapter, versioned synthetic command factory and PostgreSQL
  snapshot/repository/Unit-of-Work adapters. No real Provider or customer-data path was composed.
- Extended the shared I02 transaction so Requirement writes, provenance merges, conflict Domain
  Events and `Job → succeeded` commit together.
- Added migration `0027_requirement_gen_runtime`: the active revision constraint and least-privilege
  Worker authority (Context read; Requirement read/specific insert/source-ref update; conflict
  Outbox insert). The migration was downgrade/re-upgrade verified.
- Added unit, contract and PostgreSQL tests plus synchronized ADR, data-model, Worker and index
  documentation.

## Structure Preservation

- Preserved `Internal Application scheduler → Job/Outbox ports ← SQLAlchemy Infrastructure` and
  `Celery → Consumer → shared provider-neutral I02 use case → PostgreSQL ports`.
- Domain/Application code imports no Celery, SQLAlchemy, Redis or Provider SDK.
- Queue and Outbox envelopes remain identifier-only; all Tenant, Context and Requirement data are
  loaded from PostgreSQL by `job_id`.
- No public router, OpenAPI endpoint, AI-01 chaining, hosted task registration, new deployable,
  customer-data path, paid Provider, Primary/Fallback or automatic Queue retry was added.

## Senior Review

- **Contract parity:** PASS. Durable identities, exact revision binding, internal-only trigger,
  synthetic-only adapter and all deferred gates match ADR-060.
- **Atomicity:** PASS. Scheduler Job/Outbox creation is one transaction. Final Requirement merge,
  conflict Outbox writes and Job success are a second single transaction; forced commit failure
  exposes no Requirement and leaves the same running Job recoverable.
- **Concurrency/idempotency:** PASS. A partial unique index prevents two active Jobs for the same
  Account/Project/Context Version. The execution guard suppresses concurrent/completed delivery;
  ADR-031 merge rules prevent duplicate committed Requirements.
- **Tenant/security:** PASS. Worker resolves and rechecks Account/Project/Context through the Job;
  Outbox reference validation is exact. Worker grants were tightened during review from broad
  table mutation to named insert columns and `UPDATE(source_refs)` only.
- **Privacy/cost:** PASS. Queue/Outbox/log contracts exclude Context and Requirement content. The
  only Provider is synthetic, tokens and cost are zero, and hosted composition cannot invoke it.
- **Migration/recovery:** PASS. Fresh upgrade, downgrade to 0026 and re-upgrade to head passed on
  PostgreSQL 16; the final Worker privilege projection was inspected.
- **Scope:** PASS. Public trigger, AI-01 chaining and Product/Hosted AI remain explicitly deferred.

## Verification

- Contract suite: 4 passed.
- Focused API suites: 30 passed; focused Worker suites: 14 passed.
- PostgreSQL suites: 10 passed across I02 regression, internal scheduling, atomic finalization,
  duplicate delivery, commit recovery and migration recovery.
- Full API: 444 passed / 150 skipped; full Worker: 144 passed / 14 skipped.
- Contract CI: 185 passed; Eval: 35 passed; Web: 40 passed.
- API/Worker Ruff and strict mypy passed; Web/API/Worker production build passed.
- Mandatory `npm test`, `npm run validate`, secret scan and `git diff --check` passed in the final
  documented run; exact commands/results are in the linked report.

## Remaining Risks

- Real Provider quality, customer-data review and paid-call post-response recovery are not proven
  and remain release blockers for Product AI activation.
- The task is intentionally absent from hosted composition; the foundation is not a Staging Product
  feature until a later public/internal trigger and activation contract are approved.
- Queue-level automatic retry remains disabled. Controlled recovery after a fake-provider commit
  interruption does not authorize re-invoking a paid Provider.
