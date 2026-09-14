# Development Record: 0063 — Upload Security Suite

- **Status:** IN PROGRESS
- **Increment:** S1-L04
- **Source sync date:** 2026-09-14
- [Test report](./test-report.md)

## Scope

Implement the approved contract-first security regression suite for feature-gated UTF-8 TXT upload.
The suite covers input and filename abuse, private-storage boundaries, Tenant isolation,
idempotency, compensation, fail-closed activation and leakage. TXT parser runtime, Source
list/archive/retry APIs and Context Inbox UI remain out of scope.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L04; synchronized 2026-09-14
- [Security & Threat Model v1.0](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit) — T-UP-01 through T-UP-05, SEC-07, SEC-15; modified 2026-08-17; synchronized 2026-09-14
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-CTX-003/004 and TC-STO-001 through TC-STO-008; modified 2026-08-17; synchronized 2026-09-14
- [Supabase Storage Buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals) and [Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control) — current private-bucket/RLS behavior; checked 2026-09-14
- Owner-approved 0062 D03 contract and 0063 sequencing/gate dated 2026-09-14
- [ADR-049](../../adr/ADR-049-txt-upload-foundation.md) and [ADR-050](../../adr/ADR-050-upload-security-suite.md)

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6301 | S1-L04; T-UP-01; TC-STO-005 | Exact extension/MIME, strict UTF-8 and inert-text validation corpus | TC-6301 |
| REQ-6302 | S1-L04; T-UP-01/05; TC-CTX-003; TC-STO-006 | Exact byte/character boundaries and oversize rejection before storage | TC-6302 |
| REQ-6303 | T-UP-02; TC-STO-002/007 | Basename/control validation and server-generated object key | TC-6303 |
| REQ-6304 | T-UP-03/04; TC-STO-001/003/004 | Private-only adapter surface, no ACL/upsert/public or signed URL, hosted bucket evidence | TC-6304 |
| REQ-6305 | T-TEN-02; TC-TEN-003 | Foreign Project uses tenant-scoped safe 404 and performs no storage operation | TC-6305 |
| REQ-6306 | T-API-02; SEC-10 | Same request replay and different-payload conflict without duplicate object/state | TC-6306 |
| REQ-6307 | Failure/recovery baseline | Commit failure compensation and observable orphan-repair signal | TC-6307 |
| REQ-6308 | Secure by default; T-LOG-01; SEC-15 | Feature flag fail-closed and negative filename/content/object URL/credential logging tests | TC-6308 |
| REQ-6309 | Owner-approved durable allocation contract | Stable pre-upload identity, atomic claim, unknown-outcome recovery and no blind re-upload | TC-6309 |

## Assumptions and Clarifications

- The owner froze TXT identity as exact `.txt` + normalized `text/plain` + strict UTF-8 + approved
  text-safety validation. No arbitrary keyword or magic-signature blacklist is added.
- The owner requires private-bucket and unauthenticated-access evidence before Staging activation.
- The Supabase project `aria-ai-staging` was `INACTIVE` on 2026-09-14 and the read-only bucket query
  timed out. The owner restored it and last reported `COMING_UP`; hosted evidence remains pending
  until the project is ready and the gate runtime receives secrets from its secure source.
- The owner froze the durable Upload Allocation state machine and stable-ID behavior on 2026-09-14.
  Recovery reconciliation, lease/stale timeout and automatic retry remain explicitly undefined.
- D04 and all missing runtime/list/archive/retry semantics remain explicitly deferred.

**Unapproved assumptions:** None

## Changes

- Added ADR-050 and a CI-wired static contract that freezes the complete L04 attack/evidence
  matrix and prevents accidental activation or provider/public-download scope expansion.
- Expanded Domain tests for MIME spoofing, mixed/uppercase extensions, invalid UTF-8, PE/ELF/ZIP
  binary masquerading, inert executable-looking text, byte/character boundaries and filename abuse.
- Added an HTTP regression that maps both near-limit and multi-megabyte uploads to the same
  `413 FILE_TOO_LARGE` contract before invoking Application code. The router now uses the parsed
  upload size before reading/dispatching the file.
- Added exact-response leakage assertions and negative validation-log tests for filename, customer
  content, storage reference/key and public/signed URL vocabulary.
- Added a real PostgreSQL Tenant A/B upload test proving a foreign Project is safe-not-found before
  any object write and persists no Source, Version, Job or Outbox row.
- Added an opt-in hosted Supabase evidence test. It uploads a generated sentinel using server-side
  S3 credentials, verifies the conventional public object endpoint denies access and deletes the
  sentinel in `finally`. It is skipped unless the explicit hosted-evidence environment is enabled.
- Added `file_upload_allocations` and a provider-neutral allocation repository. Allocation is
  committed before Storage, owns stable Source/Version/Job/object identities, uses an atomic upload
  claim and is protected by RLS plus revoked Data API grants.
- Split definite Storage failures from unknown remote outcomes. Definite retryable failure returns
  the same allocation to `allocated`; a read timeout/closed connection moves it to
  `recovery_required`, and subsequent same-key calls never issue another `PutObject`.
- Made the final Source/Version/Job/Outbox write and allocation `committed` transition atomic.
  Successful compensation restores the same allocation to `allocated`; failed compensation makes
  it recovery-required. Concurrent claim losers cannot perform a duplicate upload.

## Structure Preservation

- No endpoint, file type, parser runtime, public URL, signed URL, provider retry or Inbox UI is added.
- Validation remains Domain-owned; orchestration remains Application-owned; Supabase/S3 details stay
  in Infrastructure; Tenant authority remains the authenticated active Membership and scoped Project.
- `TXT_UPLOAD_ENABLED` remains false by default and in documented Staging configuration.

## Senior Review

**Status:** PASS for code and local PostgreSQL; hosted evidence remains open.

Senior review traced validation before storage, request-to-Application error mapping, key
construction, tenant-scoped Project resolution, idempotency reservation, compensation and all
storage-related log/response surfaces. It found and fixed one High issue: files above the approved
limit could reach multipart parsing and then be represented inconsistently; the route now maps any
parsed upload above 200,000 bytes to the stable 413 contract before dispatch.

Review identified and closed two High concurrency/recovery defects. First, upload identity formerly
rolled back with the business transaction, allowing a new object key after an unknown `PutObject`
outcome. Durable allocation now survives that failure. Second, a losing concurrent claimant could
observe the winner's `uploading` state and mistake it for its own successful claim. The Application
now carries the atomic transition result separately and only the actual winner calls Storage.

The review also preserves the earlier retry contract: known failed transient operations can retry
using the same allocation, while an unknown outcome is non-retryable until an explicit future
reconciliation workflow is approved. No content-bearing value, filename, object key or provider
detail is added to logs or public responses.

## Verification

Local contract, Domain/Application/API/adapter, real PostgreSQL concurrency/Tenant/RLS, migration
round-trip, lint, strict type check, CI, eval, Web, API, Worker, build, secret-scan and whitespace
checks executed successfully. Supabase is healthy and the private bucket flag is confirmed, but the
hosted sentinel/anonymous-denial evidence remains unavailable. Exact current evidence is in
[test-report.md](./test-report.md).

## Remaining Risks

- Hosted bucket privacy and anonymous denial cannot be marked PASS until restored Supabase Staging
  is ready and the opt-in gate runs with secrets injected by its runtime.
- The Python vulnerability audit remains `INCOMPLETE / ENVIRONMENTAL FAILURE` due the documented
  TLS/PyPI availability issue; this is not represented as PASS.
