# ADR-050: TXT Upload Security Gate and Hosted Storage Evidence

- **Status:** Accepted
- **Date:** 2026-09-14
- **Decision owners:** Product owner and Engineering
- **Related:** S1-L04, S1-D03, ADR-049

## Context

The approved TXT upload foundation accepts one small UTF-8 text file through a feature-gated,
tenant-authorized and idempotent API command. The canonical security baseline classifies malicious
uploads, path traversal, public bucket exposure, cross-Tenant object access and parser exploitation
as High or Critical threats. It also makes public object exposure a release blocker.

Supabase documents that private buckets are the default and that downloads from them require either
an authorized request subject to access control or a time-limited signed URL. Server-side S3
credentials bypass Storage RLS and therefore remain restricted to the Infrastructure adapter.

## Decision

- S1-L04 is a layered security gate covering Domain validation, HTTP error behavior, Application
  atomicity/idempotency, Tenant scoping, the Supabase S3 adapter boundary and hosted bucket state.
- TXT content identity is determined by exact lowercase `.txt`, normalized `text/plain`, strict
  UTF-8 decoding and text-safety validation. No executable keyword blacklist or unapproved magic
  signature list is introduced.
- Binary executable masquerading is rejected when strict UTF-8 or approved text-safety validation
  fails. Executable-looking valid text is treated as inert data and is never executed or previewed.
- The server-generated object key contains only environment and trusted server/Tenant UUIDs. The
  display filename is never decoded into, concatenated with or otherwise used as an object key.
- The adapter performs only a private `PutObject` without ACL, public URL, signed URL or upsert
  options. Public/signed download capability is outside D03/L04.
- Missing and foreign Projects remain indistinguishable through the tenant-scoped lookup; no object
  upload or storage existence probe occurs before authorization.
- Same-key/same-payload retry is an exact replay. Same-key/different-payload fails before a second
  upload. A failed database commit triggers external object compensation and cleanup failure remains
  an observable failure, never a false success.
- File upload uses a durable, tenant-scoped allocation with stable server-generated `source_id`,
  `source_version_id`, `job_id` and `object_key`. Its lifecycle is `allocated -> uploading ->
  committed`, with `recovery_required` for an unknown remote outcome or failed compensation.
- Allocation is committed before `PutObject`, and `allocated -> uploading` is an atomic claim. A
  concurrent request that did not acquire the claim cannot upload. An existing `uploading` state is
  retryable only as a later client attempt; it never causes an immediate blind re-upload.
- A read timeout or connection close after dispatch has an unknown `PutObject` outcome and moves the
  allocation to `recovery_required`; same-key retries reuse the allocation and do not call Storage.
  No stale timeout, lease or reconciliation policy is invented in L04. A definite retryable failure
  returns the same allocation to `allocated`.
- Source, Version, Job, Outbox and the `committed` allocation transition share one transaction. If
  that transaction fails after upload, successful compensation returns the same allocation to
  `allocated`; failed compensation moves it to `recovery_required`. Neither path creates new IDs.
- Only expired `committed` allocations may be replaced after the approved 24-hour idempotency
  window. Unresolved `uploading` and `recovery_required` allocations never auto-expire into a new
  object key.
- Automated tests prove the code boundary. A hosted check must separately prove that the configured
  Supabase bucket is private and an unauthenticated object request is denied. Code-level evidence
  must not be presented as hosted-provider evidence.
- `TXT_UPLOAD_ENABLED` stays false in defaults and Staging until every L04 release-blocking check,
  including hosted storage evidence, passes.
- Logs use bounded allowlisted metadata and never include filename, object key/URL, customer text,
  object bytes, credentials, JWT or multipart payload.

## Consequences

The deterministic suite can run in CI without provider credentials. Staging activation has an
explicit external evidence gate, so a paused or unreachable Supabase project cannot be reported as
security PASS. Restoring or configuring that project remains an operator action.

The allocation table is an upload-specific security state machine rather than a second response
cache. It is RLS-enabled, unavailable to `PUBLIC`, `anon` and `authenticated`, and linked to the
tenant Project by a restrictive composite foreign key. It intentionally has no FK to Source,
Version or Job because it must exist before those business records.

## Deferred

- TXT parser runtime, parser retry/recovery semantics and Source list/archive/retry APIs.
- Context Inbox UI.
- PDF/DOCX, malware scanning, general file-signature classification and executable preview.
- Signed download URLs or any public object delivery contract.
- Recovery/reconciliation command, claim lease, stale-upload timeout or automatic recovery worker.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L04
- [Security & Threat Model v1.0](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit) — T-UP-01 through T-UP-05, SEC-07, SEC-15
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-CTX-003/004, TC-STO-001 through TC-STO-008
- [Supabase Storage Buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals) — private/public access model
- [Supabase Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control) — RLS and trusted server credentials
- Owner-approved 0063 sequencing and gate dated 2026-09-14
