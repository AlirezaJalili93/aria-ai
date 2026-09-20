# ADR-051: TXT Parser Consumer and Crash Recovery

- **Status:** Accepted
- **Date:** 2026-09-15
- **Increment:** 0064 / S1-F01, S1-F02, S1-E04 integration
- **Supersedes:** the deferred content-hash algorithm in ADR-012 and ADR-019; the unapproved
  `max_attempts=3` Parser Job creation value

## Context

The approved parser already normalizes Persian text deterministically, while Context ingestion
atomically creates a `context_source_parse` Job and an Outbox event. The missing boundary is the
controlled Worker consumer that resolves PostgreSQL-authoritative input, revalidates stored TXT,
suppresses concurrent delivery, survives Worker loss and finalizes Source, Version and Job without
partial success. Continuous Outbox scheduling remains a separate decision.

## Decision

- Queue messages use version `1` and contain only `message_version`, `outbox_event_id` and `job_id`.
  Account, Project, Source and Version authority is loaded from PostgreSQL; message fields never
  establish Tenant scope.
- `context_source_parse` is the only admitted Job type. Its `payload_ref` contains exactly
  `source_id` and `source_version_id`.
- A PostgreSQL session advisory lock derived from `job_id` is the Infrastructure implementation of
  the existing atomic `JobExecutionGuard`. A live holder yields `already_in_progress`; terminal Jobs
  yield `already_completed`. Disconnect or process loss releases the lock, so redelivery can recover
  the same running Job without a lease duration or new persistence table.
- The processing transition is a short transaction. The parser and private Storage read run outside
  database transactions while the session advisory lock remains held.
- Success atomically transitions `context_sources`, `context_source_versions` and `jobs` to
  `ready`, `ready` and `succeeded`. A failed final commit leaves the previously committed processing
  state recoverable; no Source, Version or Job is recreated.
- Expected input failures atomically transition the same rows to `failed`. Persisted `error_code` is
  bounded and `error_detail` remains null. A failure to commit that transition also leaves the Job
  recoverable rather than presenting false terminal state.
- Text Sources revalidate persisted `raw_text`. File Sources require the already-approved TXT
  contract, read bytes only through a private provider-neutral object reader, enforce the 200,000
  byte bound, decode strict UTF-8, apply the shared text-safety rules, normalize and hash.
- `content_hash` is lowercase SHA-256 over canonical text encoded as UTF-8.
- Parser automatic retry is disabled. Newly created Parser Jobs persist `max_attempts=1` only as the
  database representation of one execution policy; neither Celery autoretry nor task retry is used.
  Worker-loss redelivery recovers the same logical attempt and does not increment it again.
- Queue wait is recorded only for the first `queued -> running` transition. Recovery of an already
  running Job does not create a second queue-wait measurement.
- Logs use `source_version_id` for Version identity. Customer text, filename, object key/URL,
  credential and free-form provider error content are forbidden.

## Database authority

`aria_worker` remains `NOSUPERUSER`, `NOBYPASSRLS` and receives only `SELECT, UPDATE` on
`jobs`, `context_sources` and `context_source_versions`, plus read-only `SELECT` on the referenced
`outbox_events` row and exact RLS policies for those commands. It receives no INSERT or DELETE
authority on these tables. The consumer performs same-tenant Source/Version joins and validates all
authoritative identifiers before mutation.

## Deferred

- Continuous Outbox relay scheduler, cadence, batch size, ordering, claim/lease, concurrent relay
  policy, crash recovery and deployment topology.
- Queue producer mapping and Celery Parser task name/registration.
- Hosted automatic processing and Staging feature activation.
- Manual Retry API, backoff, automatic retry, dead-letter and exhausted-message policy.
- Source list/archive/retry APIs and Context Inbox UI.
- PDF, DOCX and any non-TXT file parser.

## Sources

- Sprint 1 Technical Backlog v1.0 — S1-D01/D02/D03, S1-E04 and S1-F01/F02/F04; Drive revision
  `ANLCKQlujALNdyJZbNLOedCGxjlG8UwcE_pkF1cT3bEgoVASWO7u08ikQ51FIfnZfHk9DV_8iMg67AayWjRPBbEjFROHXn7_gAUAEruNFw`
- Detailed Data Dictionary v1.0 — Context Source/Version and Job state; Drive revision
  `ANLCKQkdVXB86IryIlAP0IbwWyfEm4LviHOuB6kpQmpCk2he_wXipgFKuKlqh_60_yS_vcbiDLmhLldoRUjp2rUNoo7X5V6b-yiu1uufGQ`
- Final System Architecture v2.0 — durable Worker and PostgreSQL source-of-truth boundary
- Test Strategy & Test Case Master v1.0 — TC-JOB-002/005/008/010 and TC-CTX-005
- ADR-012 through ADR-020, ADR-049 and ADR-050
- Owner approval dated 2026-09-15
- Current Supabase S3 compatibility/authentication/private-bucket documentation, checked 2026-09-15

**Unapproved assumptions:** None
