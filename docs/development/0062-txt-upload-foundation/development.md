# Development Record: 0062 — TXT Upload Foundation

- **Status:** COMPLETE
- **Increment:** S1-D03
- **Source sync date:** 2026-09-13
- [Test report](./test-report.md)

## Scope

Implement the approved, feature-gated private UTF-8 TXT upload on the existing Context Source
endpoint, including exact multipart validation, provider-neutral object storage, Supabase S3
Infrastructure wiring, transactional Source/Version/Job/Outbox persistence, idempotency,
compensation and safe observability. F03 parsing and L04 security release validation remain outside
this increment.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D03, S1-F03 and S1-L04; synchronized 2026-09-13
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — multipart upload, async Job response, status/error and security baselines; synchronized 2026-09-13
- Repository mirrors: architecture/data model, API OpenAPI baseline, ADR-012 and ADR-014
- Owner-approved 0062 base and supplemental contracts dated 2026-09-13
- [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication), [S3 compatibility](https://supabase.com/docs/guides/storage/s3/compatibility), [S3 uploads](https://supabase.com/docs/guides/storage/uploads/s3-uploads), [standard uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads), and [Storage access control](https://supabase.com/docs/guides/storage/security/access-control) — reviewed 2026-09-13
- [ADR-049](../../adr/ADR-049-txt-upload-foundation.md) — frozen implementation decision

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6201 | S1-D03; owner §1/§3 | Existing route accepts exact JSON or exact two-part multipart | TC-6201, TC-6202 |
| REQ-6202 | Owner §1/§2/§6/§7 | Lowercase `.txt`, normalized `text/plain`, strict UTF-8, NFC basename and text-safety validation | TC-6203, TC-6204 |
| REQ-6203 | Owner §2 | 200,000-byte pre-processing bound and 50,000-character post-decode bound | TC-6205 |
| REQ-6204 | Owner §4/§5/§10 | Provider-neutral port, private Supabase S3 adapter and server-generated tenant key | TC-6206, TC-6207 |
| REQ-6205 | Owner §8 | Mandatory 24-hour idempotency; same semantics replay; changed bytes conflict; no duplicate effects | TC-6208, TC-6217 |
| REQ-6206 | Owner supplemental §4 | Upload before business commit; mandatory delete compensation and discoverable cleanup incident | TC-6209, TC-6210 |
| REQ-6207 | Owner supplemental §5 | 5s/30s timeouts, no automatic SDK/API upload retry and no upsert | TC-6211 |
| REQ-6208 | Owner §3/§9 | Relative status URL and exact 413/415/422/503 stable error mappings | TC-6212, TC-6213 |
| REQ-6209 | Owner §11 | `TXT_UPLOAD_ENABLED=false`; incomplete enabled configuration fails closed | TC-6214 |
| REQ-6210 | Owner §12 | Approved lifecycle logs and strict content/filename/key/credential negative leakage | TC-6215 |
| REQ-6211 | S1-D03/F03/L04 boundary | PDF/DOCX, parsing/BOM normalization, automatic retry and activation remain deferred | TC-6216 |

## Assumptions and Clarifications

The owner froze multipart parts, status mappings, relative status URL, external compensation,
cleanup-incident behavior, timeouts and retry ownership on 2026-09-13. Lowercase `.txt` follows the
approved exact `extension == .txt` contract. The Source integrity checksum and parser content hash
remain unset because D03 approves a request fingerprint but does not redefine either stored hash.

**Unapproved assumptions:** None

## Changes

- Added strict TXT upload validation for exact lowercase `.txt`, normalized `text/plain`, UTF-8,
  the approved byte/character bounds, NFC display filenames and existing text-safety rules.
- Added the provider-neutral `ObjectStoragePort` and a Supabase S3 Infrastructure adapter using
  SigV4, path-style addressing, 5-second connect and 30-second read timeouts, and one total SDK
  attempt. The adapter sends no public ACL, signed URL or upsert signal.
- Extended the existing Context Source route with the exact two-part multipart contract while
  preserving JSON text ingestion. Success returns the approved relative Job status URL; failures
  use the stable 403/413/415/422/503 envelopes.
- Implemented upload-first orchestration followed by one Source/Version/Job/Outbox/idempotency DB
  transaction. A failed commit triggers object deletion; failed cleanup emits a critical,
  identifier-only incident and never returns false success.
- Added safe lifecycle observability fields and negative leakage coverage. Filename, content,
  object key/URL, credentials and raw multipart data are excluded.
- Added unit, HTTP, adapter and real PostgreSQL concurrency tests proving one logical pipeline and
  one object for concurrent replay of the same semantic upload.
- Kept `TXT_UPLOAD_ENABLED=false` as the default and made enabled configuration fail closed.
- During the final dependency gate, upgraded `next` and `eslint-config-next` from 16.3.1 to 16.3.5
  and resolved `sharp` 0.35.4 plus `js-yaml` 4.3.2. The repeated npm audit then reported zero
  vulnerabilities.

## Structure Preservation

- Existing modular-monolith flow remains Context Domain → Application Port/Use Case → Infrastructure.
- The existing public route, Source/Version schema, Job type and Outbox event are reused.
- No new deployable, database table, public Storage route, signed URL or parser is introduced.

## Senior Review

**PASS.** The final review confirmed:

- Domain/Application contain no Supabase or boto types; provider behavior remains in Infrastructure.
- Tenant authorization and the actor-aware idempotency reservation precede object upload; no
  out-of-tenant existence lookup is introduced.
- The deterministic object key contains only environment and server/tenant UUIDs, never the
  customer filename.
- Job and Outbox payloads contain only IDs/version metadata, while customer content and storage
  references remain outside the async envelope.
- Concurrent same-key requests serialize at the PostgreSQL idempotency boundary and replay without
  a second logical or storage effect; changed bytes produce the approved conflict.
- Upload failure commits no business state, and post-upload transaction failure always attempts
  external compensation. Cleanup failure is discoverable from safe internal IDs.
- The adapter performs one request attempt and maps transient versus configuration/auth failures to
  bounded retryability without leaking provider responses.
- Existing JSON behavior, modular-monolith structure and all documented deferred boundaries remain
  intact. No unapproved product behavior was added.

## Verification

**PASS.** Repository lint, typecheck, contract/eval/web/API/worker tests, production build,
architecture validation, secret scan and npm vulnerability audit passed. The complete command and
count evidence is recorded in the linked test report.

## Remaining Risks

- Staging activation remains blocked until F03 and the S1-L04 security suite pass.
- Bucket privacy and staging credential scope require hosted evidence in L04; no public URL is
  created or exposed by this implementation.
- The combined dependency-scan wrapper could not download `pip-audit==2.10.1` because the execution
  environment terminated every PyPI TLS handshake. Its npm phase passed with zero vulnerabilities;
  the Python audit must be rerun in CI or an environment with PyPI connectivity. This is recorded as
  tooling/network evidence, not silently reported as a passing Python audit.
