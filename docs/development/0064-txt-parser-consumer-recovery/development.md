# Development Record: 0064 — TXT Parser Consumer and Recovery

- **Status:** Completed
- **Increment:** S1-F01/F02 + S1-E04 integration
- **Source sync date:** 2026-09-15
- [Test report](./test-report.md)

## Scope

Implement the approved controlled TXT Parser consumer, PostgreSQL-backed concurrent-delivery guard,
private stored-object revalidation, canonical hashing and atomic Source/Version/Job finalization.
Continuous Relay scheduling and hosted automatic processing remain disabled.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D01/D02/D03, S1-E04 and S1-F01/F02/F04; Drive revision `ANLCKQlujALNdyJZbNLOedCGxjlG8UwcE_pkF1cT3bEgoVASWO7u08ikQ51FIfnZfHk9DV_8iMg67AayWjRPBbEjFROHXn7_gAUAEruNFw`; synchronized 2026-09-15.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Context Sources, Source Versions, Jobs and Outbox; Drive revision `ANLCKQkdVXB86IryIlAP0IbwWyfEm4LviHOuB6kpQmpCk2he_wXipgFKuKlqh_60_yS_vcbiDLmhLldoRUjp2rUNoo7X5V6b-yiu1uufGQ`; synchronized 2026-09-15.
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — Durable Worker Pool, transactional boundaries and PostgreSQL source of truth; synchronized 2026-09-15.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-JOB-002/005/008/010 and TC-CTX-005; synchronized 2026-09-15.
- [ADR-051](../../adr/ADR-051-txt-parser-consumer-recovery.md)

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6401 | S1-F01/F02; ADR-019/051 | Controlled versioned Queue message and PostgreSQL-authoritative input | TC-6401 |
| REQ-6402 | S1-E04; TC-JOB-005/008 | Session advisory lock, concurrent suppression and crash recovery | TC-6402 |
| REQ-6403 | Owner 0064 decision; ADR-051 | Atomic Source/Version/Job processing, success and failure transitions | TC-6403 |
| REQ-6404 | S1-D03/L04; ADR-049/050 | Private TXT read and strict UTF-8/text-safety revalidation | TC-6404 |
| REQ-6405 | S1-F02; owner 0064 decision | Lowercase SHA-256 over canonical UTF-8 | TC-6405 |
| REQ-6406 | Owner 0064 decision | Automatic retry disabled and Parser Jobs created with one attempt | TC-6406 |
| REQ-6407 | S1-F04; logging baseline | First-attempt queue wait and leakage-safe Version telemetry | TC-6407 |
| REQ-6408 | Security/RLS baseline | Least-privilege `aria_worker` SELECT/UPDATE policies only | TC-6408 |

## Assumptions and Clarifications

- All runtime, hash, recovery, stored-input and scheduler boundaries are frozen in ADR-051.
- Continuous Relay scheduling and Hosted automatic processing are explicitly deferred.

**Unapproved assumptions:** None

## Changes

- Added accepted [ADR-051](../../adr/ADR-051-txt-parser-consumer-recovery.md), including the exact
  Queue envelope, advisory-lock recovery, SHA-256 rule, atomic finalization and explicit Scheduler/
  Producer deferrals.
- Added `TxtParserConsumer` and provider-neutral Store/Object Reader ports. The Application validates
  the exact v1 message, resolves authoritative state from PostgreSQL, revalidates untrusted stored
  TXT, normalizes Persian text, hashes canonical UTF-8 and emits bounded lifecycle telemetry.
- Added a PostgreSQL Job Store and session advisory-lock Guard. Processing, terminal success and
  terminal input failure are short transactions; parsing and private Storage reads occur outside a
  database transaction while the Job lock remains held.
- Added a Supabase S3-compatible private `GetObject` adapter with path-style SigV4, 5-second connect
  timeout, 30-second read timeout, no SDK retry and bounded stream reads.
- Added a controlled one-message runner and a composition factory. No Celery Parser task name,
  Producer mapping, beat schedule or continuous relay was registered.
- Added migration `0021_txt_parser_worker_access`: `aria_worker` gets only `SELECT/UPDATE` on Parser
  state tables and read-only access to the referenced Outbox row; INSERT/DELETE remain denied.
- Disabled automatic Parser retry at Job creation and changed newly created Parser Jobs from the
  previous unapproved three-attempt value to the one-execution database representation.
- Centralized the approved Text Context safety rules for API and Worker reuse while retaining
  after-normalization empty validation and the original public API constant.
- Corrected Parser structured log identity from the misleading `source_id` alias to
  `source_version_id`, added Job trace binding, and added the bounded `job_type` log field.
- Added contract, Application, Storage, controlled-runner and real PostgreSQL tests, plus locked
  Worker S3 dependencies.

## Structure Preservation

- PASS: Worker Application imports no Celery, boto3, SQLAlchemy, asyncpg, Supabase or provider SDK;
  concrete database and Storage behavior remains in Infrastructure.
- PASS: the shared safety module contains deterministic validation only and imports no API/Worker
  framework code.
- PASS: Source/Version/Job writes stay inside the existing modular-monolith boundaries and use the
  existing persistent entities; no second recovery/idempotency table was introduced.
- PASS: no public API, UI, new deployable or Google Drive structure changed.
- PASS: hosted automatic processing, task registration, Producer mapping, Relay Scheduler and retry
  policy remain explicitly deferred.

## Senior Review

- PASS: Queue messages carry no Tenant authority; Job, Outbox, Source and Version are joined and
  validated from PostgreSQL before mutation.
- PASS: a live advisory-lock owner suppresses concurrent delivery; session loss releases ownership;
  terminal Jobs are successful no-ops; recovery reuses the same Job/Source/Version and does not
  increment the logical attempt.
- PASS: success and expected input failures update Source, Version and Job atomically. A failed
  prepare/finalization commit rolls back and leaves the prior queued/running state recoverable.
- PASS: stored bytes are bounded, decoded with strict UTF-8 and passed through the shared safety and
  normalization contracts before lowercase SHA-256 is calculated.
- PASS: `aria_worker` receives no direct INSERT/DELETE capability on Parser state and cannot mutate
  Outbox rows.
- PASS: logs contain correlation and internal identifiers but not customer text, filename, object
  reference/URL, credential, provider detail or raw exception text.
- FIXED DURING REVIEW: an initially drafted Celery task name and automatic runtime registration were
  removed because Producer/task naming is not yet approved. Only the explicitly allowed controlled
  runner remains.
- FIXED DURING REVIEW: stale contract assertions were aligned with the already-approved
  `source_version_id` and anonymous private-bucket sentinel naming; gates now verify current
  canonical behavior rather than the superseded aliases.

## Verification

All focused, regression, migration, lint, type, build, dependency and secret gates passed. The real
PostgreSQL suite was run separately with `TEST_DATABASE_URL` against PostgreSQL 16 so its three
environment-gated tests are backed by execution evidence. See the linked test report for commands
and results.

## Remaining Risks

- Hosted automatic processing remains intentionally unavailable until Queue Producer/task naming
  and Continuous Relay Scheduler contracts are approved.
- Automatic retry/backoff, ACK/requeue behavior after an ordinary task failure, manual Retry API and
  dead-letter/exhaustion policy remain unimplemented by decision.
- The Parser metrics port receives first-attempt queue wait when a sink is injected; selection and
  wiring of a concrete Parser metric backend remain deferred by ADR-020.
- Hosted Supabase `GetObject` execution is not claimed by this increment. Private-bucket upload,
  anonymous denial and cleanup evidence belongs to the already completed 0063 security gate.
- The full API suite retains one upstream Starlette/httpx deprecation warning; it does not affect
  test outcomes and dependency migration was not part of 0064.

**Final status:** PASS
