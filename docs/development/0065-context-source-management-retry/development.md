# Development Record: 0065 — Context Source Management and Explicit Retry

- **Status:** Completed
- **Increment:** S1-D04 backend prerequisites + S1-E05 explicit Parser recovery
- **Source sync date:** 2026-09-15
- [Test report](./test-report.md)

## Scope

Implement the approved Tenant-scoped Context Source list/detail projections, authorization-aware
soft archive, and explicit retry of the one approved recoverable TXT Parser failure. Preserve
Source Versions, Storage objects, provenance and failed Job history. Automatic retry, continuous
Outbox scheduling, physical Storage GC and the D04 UI remain deferred.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D04 and S1-E05; synchronized 2026-09-15.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Context Source list/detail/delete and Job status/retry; synchronized 2026-09-15.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Context Source, Source Version and Job persistence; synchronized 2026-09-15.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active membership, roles and Tenant-safe denial; synchronized 2026-09-15.
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — Context processing and recovery states; synchronized 2026-09-15.
- [ADR-052](../../adr/ADR-052-context-source-management-and-retry.md) — owner-approved canonical 0065 decisions.

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6501 | S1-D04; ADR-052 | Cursor-paginated Source list with safe summary projection | TC-6501 |
| REQ-6502 | S1-D04; ADR-052 | Source detail with latest Version, current-ready Version and latest Parser Job summaries | TC-6502 |
| REQ-6503 | Access Control; ADR-052 | Owner/Admin archive any visible Source; Member only own Source; uniform safe 404 | TC-6503 |
| REQ-6504 | Data Dictionary; ADR-052 | Soft archive preserves Versions, Storage references and downstream provenance | TC-6504 |
| REQ-6505 | S1-E05; ADR-052 | Explicit retry creates a new Job with immediate-parent lineage for the same SourceVersion | TC-6505 |
| REQ-6506 | ADR-052 | Mandatory request idempotency and one active Parser Job per SourceVersion | TC-6506 |
| REQ-6507 | API Contract; ADR-052 | Bounded retryability classification and stable public errors | TC-6507 |
| REQ-6508 | Security baseline; ADR-052 | Tenant-scoped reads/mutations, restricted self-FK and leakage-safe telemetry | TC-6508 |

## Assumptions and Clarifications

- The approved recoverable failure is exactly `PARSER_STORAGE_UNAVAILABLE` on a failed
  `context_source_parse` Job.
- `retry_of_job_id` always means immediate parent, never root lineage.
- Archive is logical only; Storage retention and physical cleanup are separate future contracts.
- Automatic retry and continuous Outbox Relay scheduling remain disabled.

**Unapproved assumptions:** None

## Changes

- Added accepted [ADR-052](../../adr/ADR-052-context-source-management-and-retry.md) and linked it
  from the ADR index.
- Added safe list/detail Application contracts and a PostgreSQL projection repository. Reads are
  scoped by `account_id + project_id`, exclude deleted Sources, use deterministic
  `(created_at, id) DESC` cursors and never expose content or Storage internals.
- Added archive policy enforcement. Owner/Admin can archive any visible Source; Member can archive
  only a Source created by the same Profile. Active Parser work blocks archive with
  `CONTEXT_SOURCE_BUSY`; repeated archive is a successful no-op.
- Added explicit Job retry with row locking, mandatory idempotency, immutable parent Jobs, a new
  child Job/Outbox record, and reset of the same Source/Version to the pending processing state.
- Added migration `0022_context_source_management` for immediate-parent Job lineage, same-Tenant
  self-reference, one-child protection, the active Parser Job partial unique index, and Source
  pagination support.
- Added the bounded Job Status retryability projection: only failed TXT Parser Storage
  unavailability is reported retryable.
- Added stable `CONTEXT_SOURCE_BUSY` and `JOB_NOT_RETRYABLE` API errors and wired the Source and Job
  routes through the existing modular-monolith composition root.
- Added contract, Application, API and real PostgreSQL tests. Updated the existing Job Status
  contract test so it inspects the public status schema rather than rejecting internal command
  correlation metadata.

## Structure Preservation

- PASS: Domain and Application code import no FastAPI, SQLAlchemy, Supabase or Queue framework.
- PASS: SQLAlchemy query/locking/index behavior remains in Infrastructure repositories and models.
- PASS: all writes occur through existing Application unit-of-work boundaries and retry emits the
  existing transactional Outbox envelope.
- PASS: no new deployable, provider SDK, Scheduler, physical deletion flow or UI route was added.
- PASS: canonical Source/Version/Job entities remain the only persistence truth; no duplicate retry
  or recovery table was introduced.
- PASS: formatter-only changes outside 0064/0065 were restored after an explicit scope audit; no
  mixed or real 0064/0065 change was restored.

## Senior Review

- PASS: public projections omit raw/canonical text, Storage reference/object URL, hashes, metadata,
  provider details, Job payload and idempotency key.
- PASS: missing, cross-Tenant and actor-invisible Sources use the same tenant-scoped query and
  outward-safe `404 RESOURCE_NOT_FOUND`; no out-of-Tenant existence probe was introduced.
- PASS: archive preserves immutable Version history and Storage lineage and cannot race active
  queued/running Parser work without a database-backed conflict.
- PASS: retry locks the failed parent, verifies its exact authoritative Source/Version payload,
  preserves the parent, reuses the same logical input and commits Job, Outbox, state reset and
  idempotency response atomically.
- PASS: the partial unique index is the final concurrency guard against two queued/running Parser
  Jobs for one SourceVersion; the direct-child unique constraint prevents divergent retry lineage.
- PASS: structured events use internal identifiers and bounded reason/status values only; filename,
  customer content, Storage reference, Job payload, provider material and idempotency key are never
  logged.
- FIXED DURING REVIEW: pre-0065 Job Status tests scanned the entire router for internal field names
  and assumed retry was always false. They now verify the public response model and the exact
  approved retryable classification.
- FIXED DURING REVIEW: an accidental repository-wide Ruff reformat was identified by comparison
  with the formatter output of `HEAD`; only verified formatter-only files outside 0064/0065 were
  restored under the owner's scoped approval.

## Verification

Contract-first tests were red before implementation and pass after implementation. Migration 0022
was upgraded, downgraded to 0021 and re-upgraded against PostgreSQL 16. The complete repository test
suite, architecture validation, lint, type, build and security gates passed. See the linked test
report for the exact commands and results.

## Remaining Risks

- D04 Context Inbox UI remains deferred until its separate UI increment.
- Continuous Outbox Relay scheduling, automatic retry/backoff, dead-letter/exhaustion policy and
  transport ACK/requeue semantics remain intentionally unimplemented.
- Physical Storage deletion, retention and orphan/GC processing require a separate approved
  contract; archive deliberately preserves objects.
- Public Job progress-stage persistence and SSE remain deferred.
- The API suite retains one upstream Starlette/httpx deprecation warning; it does not affect test
  outcomes and dependency migration is outside 0065.

**Final status:** PASS
