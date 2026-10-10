# Development Record: 0040 Context Validation Repair

- Increment ID: `0040-context-validation-repair`
- Date: 2026-09-06
- Story: S1-H03 — Repair Strategy
- [Test report](./test-report.md)

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H03; Drive modified 2026-08-17, reviewed 2026-09-06
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — bounded repair, validation pipeline, Usage Ledger and provider retry separation; Drive modified 2026-08-17, reviewed 2026-09-06
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — deterministic Fake-provider and invalid structured-output coverage; Drive modified 2026-08-17, reviewed 2026-09-06
- Owner-approved canonical H03 contract dated 2026-09-06

Repository documents are developer-facing mirrors. The linked approved Drive documents and the
explicit owner resolution above are canonical.

## Scope

Implement the approved, single-repair, provider-neutral H03 validation-repair loop and separate
semantic `repair_no` metering from Provider `retry_no`. Preserve H02 snapshot, validation and
atomic persistence semantics; do not add Provider, transport, fallback, escalation or public API.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-4001 | Bounded, versioned Repair Policy with `max_repairs=1` and explicit disabled mode | `ContextRepairPolicy`; required command fields; ADR-027 | TC-4001, TC-4002 |
| REQ-4002 | Repair only deterministic model-output defects | `_repair_reason`; validation-only catch boundary | TC-4003–TC-4007 |
| REQ-4003 | Same AI port/workflow/routing; explicit Repair prompt; no escalation/fallback | `_execute_with_repair`; `_build_repair_input_context` | TC-4008 |
| REQ-4004 | Full H02 validation and atomic persistence after Repair | shared `_validate_response`; unchanged post-validation UoW | TC-4009–TC-4011 |
| REQ-4005 | Separate append-only Usage record for every invocation with `repair_no` | `UsageRecord`; Migration 0009; SQLAlchemy Worker adapter | TC-4012–TC-4014 |
| REQ-4006 | Safe bounded Repair logging and ephemeral rejected output | `_repair_event_fields`; in-memory Repair context; ADR-027 | TC-4015 |

## Assumptions and Clarifications

The owner approved the complete H03 contract on 2026-09-06, including the distinction between
semantic Repair and Provider retry, the exact repairable reason vocabulary and the disabled-policy
failure behavior.

**Unapproved assumptions:** None

## Changes

- Added a required immutable `ContextRepairPolicy` to the Context Structuring command. Sprint 1
  accepts only explicit values `0` and `1`; policy and Repair prompt versions have no hidden
  default.
- Refactored the H02 use case to execute, meter and validate through shared methods. Repair invokes
  the same `AIExecutionPort` with the immutable original snapshot and the bounded validation reason.
- Added exact repairability classification for schema, model-produced Source Reference,
  unsupported-claim and exact-duplicate defects. Infrastructure/runtime and insufficient-context
  failures escape the Repair loop unchanged.
- Added non-retryable `CONTEXT_REPAIR_EXHAUSTED` only after an actual Repair is consumed. Disabled
  Repair preserves the original validation error.
- Added safe Repair lifecycle events. Rejected output exists only in the in-memory AI input and is
  excluded from logger, Ledger, persistence DTO, Job, Outbox, analytics and trace fields.
- Added Migration 0009 and Worker persistence mapping for non-negative `repair_no`; every original
  and Repair response is appended independently to the authoritative Usage Ledger.
- Added ADR-027 and synchronized the ADR index, Usage ADR, data-model and system-architecture
  developer mirrors.

## Architecture and Design Decisions

- Repair is orchestration inside the shared Backend Application use case, not a new Provider port
  or deployable service. The same workflow, schema, routing, cost and timeout objects are reused;
  only the explicitly supplied Repair prompt version changes.
- The try/catch boundary surrounds only candidate validation. Source snapshot resolution, Provider
  failures, Usage persistence and Context repository/UoW failures cannot accidentally initiate a
  semantic Repair.
- Repaired output enters the exact same H02 validator method. The database Unit of Work is still
  opened only after a complete valid Batch exists, so external AI execution never holds a database
  transaction and failed Repair cannot consume a Context Version.
- `retry_no` remains the technical Provider retry number reported by the AI execution result.
  `repair_no` is supplied by orchestration (`0` original, `1` first Repair); neither overwrites the
  other.
- PostgreSQL enforces `repair_no >= 0` but deliberately does not enforce the Sprint policy ceiling.
  A future approved policy can increase the limit without rewriting historical Ledger schema.

## Structure Preservation

- `web`, `api` and `worker` remain the only deployables; no service, public endpoint, Job type or
  Queue envelope was added.
- Shared Application code imports no FastAPI, SQLAlchemy, Celery, Redis or Provider SDK.
- SQLAlchemy remains confined to the existing Worker Infrastructure adapter and Alembic migration.
- H02 Source snapshot, candidate DTO, validation, atomic UoW and Worker wrapper boundaries remain
  canonical and are reused rather than duplicated.
- No Provider/model selection, retry count, fallback, escalation, entitlement, quota, task
  vocabulary or end-user Failure UX was invented.

## Senior Review

- PASS: `ContextRepairPolicy` is immutable, explicitly versioned and rejects missing versions,
  booleans, negatives and values above the approved Sprint ceiling; there is no hidden default.
- PASS: repairability is fail-closed and reason-bounded. Only errors raised after a returned model
  candidate enters validation can be classified; provider/source-resolution/ledger/repository
  errors cannot enter the loop.
- PASS: `invalid_source_reference` maps only the three model-output provenance defects emitted by
  H02 validation. `ready_source_required`, mutable-state errors and `insufficient_context` are not
  mapped.
- PASS: original and Repair calls reuse the same port and same routing/cost/timeout/workflow objects.
  Repair adds no fallback or escalation surface; technical Provider retries remain opaque inside
  the existing execution contract.
- PASS: every returned invocation is metered before downstream candidate validation. Tests prove
  independent `(repair_no,retry_no)` pairs and PostgreSQL default/constraint behavior.
- PASS: no Context transaction opens before repaired output passes the full H02 pipeline. Tests
  prove success creates one Version and exhaustion/persistence failure create none.
- PASS: logging contains only approved identifiers, versions, bounded reason, counters, duration and
  status. Secret candidate/source data is present in the in-memory Repair request test fixture but
  absent from every captured event.
- PASS: Migration 0009 preserves the append-only trigger, worker-only INSERT authority and FK
  controls from G05; upgrade/downgrade/re-upgrade and real PostgreSQL constraints pass.
- PASS: fitness-test Regexes were made newline-tolerant after review; the checked architecture
  semantics were not weakened.

## Verification

See [test-report.md](./test-report.md). Contract, Application, real PostgreSQL, Worker, regression,
lint, strict type, production build and repository validation gates passed.

## Remaining Risks

- H03 is a provider-neutral foundation. A real Provider adapter, concrete Job/Queue composition and
  public trigger remain deferred and the complete AI vertical slice is not Production-ready.
- The approved limit is one semantic Repair. Increasing it requires a new versioned policy decision,
  evaluation and cost review even though the database can store larger historical values.
- Repair KPI queries and dashboards are deferred; H03 records authoritative Ledger dimensions but
  does not introduce analytics behavior.
- Rejected output is intentionally ephemeral. Diagnosis requiring persisted encrypted evidence
  needs a separate retention/security contract.

**Final status:** PASS
