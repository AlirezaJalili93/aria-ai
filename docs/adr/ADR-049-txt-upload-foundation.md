# ADR-049: Private TXT Upload Foundation

- **Status:** Accepted
- **Date:** 2026-09-13
- **Story:** S1-D03 — File Upload

## Context

S1-D03 activates only a bounded UTF-8 TXT upload on the existing Context Source command. The
approved contract requires private Supabase Storage behind a provider-neutral port, exact
multipart input, tenant-derived object keys, idempotent logical effects, and external compensation
when storage succeeds but the database transaction fails. File Parser behavior remains in F03 and
the security release gate remains in L04.

## Decision

- `POST /api/v1/projects/{project_id}/context-sources` accepts either the existing exact JSON text
  body or multipart with exactly `source_type=file` and one `file` part. Extra parts are rejected.
- Only lowercase `.txt`, normalized `text/plain`, strict UTF-8, at most 200,000 encoded bytes and
  at most 50,000 decoded characters are accepted. Existing text-safety validation applies.
- Filename is NFC display metadata only. It is never an authorization input, parser selector,
  content-type authority or object-key segment.
- The key is exactly `environment/account_id/project_id/source_id/version_id`, using only
  server-controlled environment and tenant/resource IDs.
- `ObjectStoragePort` belongs to Application; the Supabase S3-compatible implementation belongs to
  Infrastructure. Domain/Application contain no provider SDK types.
- Supabase Storage uses SigV4 path-style addressing, explicit Region, 5-second connect timeout,
  30-second read timeout and one total SDK attempt. D03 performs no automatic retry.
- Upload completes before Source, Version, Job, Outbox and idempotency response are committed. A
  failed commit mandates an external object-delete attempt. Cleanup failure preserves the original
  request failure and emits a discoverable critical incident using only safe IDs.
- The accepted response includes a relative `/api/v1/jobs/{job_id}` `status_url`.
- The feature flag defaults to disabled and remains disabled in Staging until L04 passes.
- Object URLs, filenames, bytes, decoded text, credentials and raw multipart bodies are forbidden
  from routine logs. Provider errors are reduced to bounded operational reason codes.

## Consequences

File content remains private and outside PostgreSQL operational payloads. Client retry through the
approved Idempotency-Key is distinct from provider retry. A cleanup incident may leave an orphan
object, but its server-generated Source/Version IDs make it discoverable without logging the key or
customer filename. The L04 suite remains the activation gate.

## Subsequent refinement

ADR-050 supersedes the rollback-sensitive idempotency portion of this decision. Upload identity is
now durably allocated before `PutObject`; Source, Version, Job and Outbox remain atomic business
writes after a successful upload. This closes the unknown-outcome timeout case without changing the
public D03 request or response contract.

## Rejected

- Public or signed preview URLs in D03.
- Filename-derived keys, parser selection or MIME trust.
- Provider SDK imports in Domain/Application.
- Hidden SDK/API retry or upsert.
- Persisting an incomplete Source row before validation/upload.
- Activating PDF/DOCX or implementing parser normalization in this increment.

## Sources

- Sprint 1 Technical Backlog v1.0 — S1-D03 and S1-L04
- API Contract Specification v1.0 — upload media type, async Jobs and stable error baseline
- ADR-012 — Context Source/Version identity and fields
- ADR-014 — Context ingestion idempotency and content-free Job/Outbox boundary
- Owner-approved 0062 base and supplemental contracts dated 2026-09-13
- Supabase Storage S3 Authentication, S3 Compatibility, Standard/S3 Upload and Access Control docs,
  reviewed 2026-09-13
