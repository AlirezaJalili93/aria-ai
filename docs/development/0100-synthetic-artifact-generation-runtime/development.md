# Development Record: 0100 Synthetic Artifact Generation Worker Runtime

- Increment ID: `0100-synthetic-artifact-generation-runtime`
- Date: 2026-10-12
- Related domain: Generation / Artifact Runtime
- [Test report](./test-report.md)

## Scope

Implement the synthetic-only Artifact Generation Worker path from an identifier-only Queue
message through deterministic controlled rendering, durable private checkpointing, immutable
publication and atomic ArtifactVersion/Artifact/Job finalization. Real Providers, customer content,
public APIs and hosted activation remain prohibited.

## Source Documents

- Owner-approved frozen `0100` contract and Option 1 limited-helper security boundary, synchronized 2026-10-12.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — EP-F2 / BE-F2-01..08; synchronized 2026-10-11.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Sprint 3 §14.3; synchronized 2026-10-11.
- [ADR-082 through ADR-087](../../adr/ADR-087-synthetic-artifact-generation-runtime.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-10001 | 0100; ADR-087 | Identifier-only `artifact.generation_requested.v1` Queue contract and Celery mapping | TC-1001 |
| REQ-10002 | 0100; EP-F2 | Fixed no-shell Node CLI bridge to the controlled Renderer | TC-1002 |
| REQ-10003 | 0100; ADR-087 | Canonical Manifest v1, deterministic checkpoint archive and immutable object keys | TC-1003, TC-1004 |
| REQ-10004 | 0100 | Create-or-verify storage, manifest-last publication and read-back hashing | TC-1004 |
| REQ-10005 | 0100 | Durable checkpoint recovery without rerendering | TC-1005 |
| REQ-10006 | Option 1 | Narrow Job/Outbox-bound PostgreSQL claim/checkpoint/finalize/release helpers | TC-1006, TC-1007 |
| REQ-10007 | Option 1 | Single execution ownership, stale/replay guards and atomic finalization | TC-1008, TC-1009 |
| REQ-10008 | Option 1 | No broad Worker grants; bounded errors and no Scope/AST/storage-content leakage | TC-1010, TC-1011 |

## Assumptions and Clarifications

The owner selected Option 1 only for the Fake/Synthetic PostgreSQL gate. The shared `aria_worker`
credential remains a trusted backend principal across Tenants; the limited helper is not presented
as Production isolation after credential compromise. Risk `WORKER-CROSS-TENANT-001` remains OPEN.

**Unapproved assumptions:** None

## Changes

- Added the fixed Artifact Generation message/task vocabulary and disabled Queue automatic retry.
- Added canonical Manifest/checkpoint functions, safe bundle extraction and deterministic keys.
- Added a fixed Application-owned Node CLI bridge and versioned synthetic candidate inputs for all
  three Project types.
- Added S3-compatible create-or-verify storage with conditional writes and read-back checksums.
- Added migration `0039_artifact_generation_runtime` with checkpoint columns, active-generation
  uniqueness and four operation-specific helpers in the non-exposed `aria_internal` schema.
- Added a dedicated `NOLOGIN`, `NOBYPASSRLS` helper owner, empty function `search_path`, qualified
  references and `EXECUTE` grants only to `aria_worker`; no broad Worker table write was granted.
- Added the PostgreSQL Worker adapter using short transactions plus a session advisory lock across
  external rendering/storage work, and best-effort ownership release.
- Tightened 0099 allocation validation so Job and Outbox payloads are exactly bound to one
  ArtifactVersion and approved ScopeVersion.
- Added Contract, Domain, service and real-PostgreSQL tests for replay, concurrency, tenant/project
  mismatch, wrong events, ownership and direct-mutation denial.

## Structure Preservation

- Application imports no Node, Next.js, boto3, Celery or SQLAlchemy implementation code.
- Infrastructure owns process, storage, Queue and PostgreSQL adapters.
- Domain/Application boundaries and the existing Job/Outbox aggregates remain authoritative.
- The helper accepts no relation name, SQL fragment, arbitrary predicate or content payload.
- No endpoint, deployable service, Provider call, customer-data path or hosted activation was added.

## Senior Review

- PASS: claim commits before rendering/storage; no database transaction remains open across external
  I/O while session ownership is retained through the advisory lock.
- PASS: exact Job/Outbox/message/version/tenant/project/Artifact/Scope binding is revalidated inside
  the privileged helper before every state transition.
- PASS: checkpoint and finalization are replay-safe; successful replay is a no-op, concurrent
  ownership has one winner, and stale older recovery fails closed.
- PASS: helper owner is least-privilege and non-login; public execution and direct Worker writes are
  denied by migration and real-role tests.
- PASS: logs and errors remain bounded and contain no canonical AST, Scope content, object key/URL or
  storage content.
- OPEN RISK: the shared Worker credential is not Tenant-bound. Option 1 mitigates malformed messages
  and accidental cross-job mutation but cannot isolate a fully compromised shared credential.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- `WORKER-CROSS-TENANT-001` is OPEN and blocks claiming Production tenant isolation. Signed delivery
  capabilities and Tenant-bound Worker credentials remain deferred to a separate security review.
- Real Provider recovery, customer content and hosted activation remain NO-GO.
- Repository-wide metadata drift, if any, remains diagnostic and independent of the fresh 0039
  migration and focused PostgreSQL gate.

**Final status:** PASS
