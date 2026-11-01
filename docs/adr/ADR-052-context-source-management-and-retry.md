# ADR-052: Context Source Query, Soft Delete, and Explicit Parser Retry

- **Status:** Accepted
- **Date:** 2026-09-15
- **Increment:** 0065 — Context Source Backend Management
- **Related:** S1-D04 backend prerequisites, S1-E05, ADR-012, ADR-018, ADR-050, ADR-051

## Context

The Context Inbox needs an authorized, content-safe Source projection, reversible logical removal,
and an explicit recovery command for the bounded TXT Parser failure that is classified as
recoverable. The existing Source model already preserves immutable Versions, while the existing
Job state machine makes failed Jobs terminal. Resetting a failed Job would therefore break Job
identity, execution-guard semantics, and audit history.

## Decision

### Source reads

- `GET /api/v1/projects/{project_id}/context-sources` returns a cursor collection ordered by
  `(created_at, id) DESC`, with default limit 20 and maximum 100.
- `GET /api/v1/projects/{project_id}/context-sources/{source_id}` returns a fuller safe projection.
- Both routes require authenticated active Tenant context. Missing Project/Source and a resource
  outside the current Tenant are identical `404 RESOURCE_NOT_FOUND` responses.
- Ordinary reads exclude `status=deleted`.
- The public projection may contain Source identity/type/state/display filename/MIME/timestamps and
  summaries of the latest Version, current ready Version and latest related parser Job. It never
  contains `raw_text`, `canonical_text`, `storage_ref`, object key/URL, checksum/content hash,
  Version metadata, provider information or Job payload.
- Latest Version is the greatest `version_no` regardless of parse state. Current ready Version keeps
  ADR-012 semantics: greatest ready `version_no`. Latest Job is the newest Job for the latest
  SourceVersion by `(created_at, id) DESC`.

### Soft delete/archive

- `DELETE /api/v1/projects/{project_id}/context-sources/{source_id}` only changes Source status to
  `deleted`; Source Versions, downstream provenance and any Storage object are preserved.
- Owner/Admin may archive any visible Source in the Project. A Member may archive only a Source
  whose `created_by` equals that Member's authenticated Profile identity. A Source not visible to
  that actor returns the same safe 404 as a missing Source.
- A queued or running parser Job for the Source blocks archive with `409 CONTEXT_SOURCE_BUSY`.
- Repeating archive against the same visible Source is state-idempotent and returns 204. No
  Idempotency-Key is required for this DELETE.
- Downstream references do not block this logical archive because history remains intact. They do
  prohibit future destructive deletion unless a separate retention contract explicitly resolves
  them.
- Physical Storage GC is deferred. The Storage object is preserved in 0065.

### Explicit parser retry

- `POST /api/v1/jobs/{job_id}/retry` requires an active Tenant context and a non-empty
  `Idempotency-Key`.
- Only a terminal `context_source_parse` Job failed with `PARSER_STORAGE_UNAVAILABLE` is retryable
  in 0065. Input, empty-content and rejected-Storage failures remain non-retryable.
- Retry creates a new queued Job for the same `source_id` and `source_version_id`. It creates no
  Source, SourceVersion or Storage object. The failed parent remains immutable.
- `jobs.retry_of_job_id` identifies the immediate parent. A failed retry may itself become the
  parent of a later retry. A parent can have at most one direct child.
- At most one queued/running parser Job may exist for one SourceVersion. The database is the final
  concurrency guard against retry storms.
- The new Job, pending Outbox event, Source `uploaded` reset, SourceVersion `pending` reset and
  completed idempotency response are one transaction. The Outbox event reuses the existing
  `context_added.v1` parser envelope with the new Job ID.
- Same key and target replay the same 202 result. Reusing a key for different input returns
  `409 IDEMPOTENCY_CONFLICT`. A Job that cannot be retried returns `409 JOB_NOT_RETRYABLE`.
- Missing/cross-Tenant Job or referenced SourceVersion returns safe `404 RESOURCE_NOT_FOUND`.
- `automatic_retry = disabled`. This command does not authorize background retry.

## Database and security

- The self-reference uses the existing same-Tenant Job identity and `ON DELETE RESTRICT`.
- A partial unique index protects active parser execution per SourceVersion.
- Existing public-schema RLS remains enabled. `anon` and `authenticated` retain no direct table
  grants; API access continues through the server-side least-privilege runtime role.
- Public read projection and mutation queries are scoped by current `account_id` and `project_id`;
  they never probe an out-of-Tenant owner to explain denial.

## Observability

Safe events include `context_source.viewed`, `context_source.archived`,
`context_source.archive_blocked`, `job.retry_queued`, `job.retry_replayed` and
`job.retry_rejected`. They may include approved identifiers, bounded status/error code, role and
duration. Filename, Source content, SourceRefs, Storage reference/URL, Job payload, idempotency key
and provider content are forbidden.

## Deferred

- Physical Storage GC, retention and destructive Source deletion.
- `PARSER_STORAGE_UNAVAILABLE` automatic retry, backoff, exhausted policy and dead-letter behavior.
- Continuous Outbox relay scheduling, cadence, lease/claim and deployment topology remain deferred.
- D04 Context Inbox UI remains a later increment consuming these public contracts.
- SSE and parser progress-stage persistence.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D04 and S1-E05; read 2026-09-15
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Context Source list/detail/delete and Job retry; read 2026-09-15
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Source, Version and Job fields; read 2026-09-15
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active membership and policy-controlled Source deletion; read 2026-09-15
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — Context processing/retry/error states; read 2026-09-15
- Owner-approved 0065 contract and refinement dated 2026-09-15
- Current Supabase RLS and Data API security guidance, checked 2026-09-15

**Unapproved assumptions:** None
