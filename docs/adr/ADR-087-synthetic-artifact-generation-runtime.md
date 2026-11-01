# ADR-087 — Synthetic Artifact Generation Worker Runtime

**Status:** Accepted

**Date:** 2026-10-11
**Increment:** `0100-synthetic-artifact-generation-runtime`

## Sources

- Engineering Backlog, EP-F2 / BE-F2-01..08 — [Canonical Drive](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit)
- Engineering Master Plan, Sprint 3 §14.3 — [Canonical Drive](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit)
- ADR-082 through ADR-086.
- Owner-approved 0100 contract, 2026-10-11.

## Decision

The synthetic-only Worker uses `job_type=artifact_generation`,
`event_type=artifact.generation_requested.v1`, `delivery_channel=job_queue`, and
Celery task `aria.artifact.generate.v1`. The Queue envelope contains only
`message_version`, `outbox_event_id`, and `job_id`; automatic task retry is disabled.

Application depends on `ControlledArtifactBuilderPort`. Infrastructure invokes one fixed,
repository-owned Node CLI with fixed arguments, no shell, a bounded timeout, a restricted
environment, and a disposable directory. It accepts only canonical
`generation_ast_schema_v1` and uses the controlled 0096 Renderer.

`artifact_manifest/v1` contains exact Artifact, ArtifactVersion and approved ScopeVersion
identity, frozen contract versions, canonical AST, and sorted file metadata. Exact UTF-8 JSON
bytes use recursively sorted object keys, preserved array order and no insignificant whitespace.
The manifest must not contain its own hash. `ArtifactVersion.artifact_hash` is SHA-256 of those
exact bytes.

Every output path is relative POSIX. Absolute paths, traversal, backslashes, duplicates and
files outside the validated bundle fail closed. Private object keys are deterministic:

```text
artifacts/{account_id}/{project_id}/{artifact_id}/versions/{artifact_version_id}/
```

Build output and manifest are first stored in a deterministic private checkpoint bundle.
After read-back verification, publication creates or verifies every immutable file and publishes
the manifest last. A verified durable checkpoint is reused after redelivery, so the Renderer is
not rerun. Storage uses create-or-verify semantics: absent creates; matching checksum reuses;
mismatching checksum fails closed. Ready-version objects are never overwritten.

The durable DB marker is the exact pair `checkpoint_ref` and `checkpoint_hash`; both are absent or
both are present and valid. No canonical AST JSON is duplicated in PostgreSQL.

Finalization locks the Artifact. Current version may move only to a newer ready version. An older
recovery loses with `ARTIFACT_GENERATION_STALE` (`retryable=false`). A database guard allows one
active generation per Artifact. Finalization atomically updates the same ArtifactVersion,
Artifact current pointer and Job success.

## Limited PostgreSQL authority

The owner selected Option 1 for the synthetic PostgreSQL gate. Four operation-specific functions
in the non-exposed `aria_internal` schema claim one exact Job/Outbox pair, persist its checkpoint,
finalize the same ArtifactVersion and release its execution ownership. Their identity inputs are
only `job_id` and `outbox_event_id`; checkpoint and finalization functions additionally accept the
validated immutable storage result they must persist. The helpers verify:

- exact Job/Outbox binding, message version, `job_queue` channel and frozen Job/Event types;
- Account/Project consistency across Job, Outbox, Project, Artifact, ArtifactVersion and approved
  ScopeVersion;
- the same `generation_job_id`, expected internal payload references and valid Job/Version state;
- active execution ownership held by the same PostgreSQL session.

The helper owner is `NOLOGIN`, `NOBYPASSRLS`, has only the selected metadata columns and required
updates, uses `SECURITY DEFINER` with an empty `search_path`, and exposes `EXECUTE` only to
`aria_worker`. The Worker receives no direct Artifact/ArtifactVersion table grant. Session advisory
locking survives the short claim transaction but no transaction remains open while Node or object
storage runs. A private claim row binds finalization to the backend session holding the lock.

This is a synthetic-runtime integration boundary, not proof that the shared Worker credential is
tenant-isolated after credential compromise. Existing Worker credential and SELECT/RLS behavior
remain unchanged.

## Threat model and residual risk

| Scenario | Result |
|---|---|
| Tenant user targets another Tenant's Artifact/Job | deny through authenticated tenant boundary |
| Mismatched or manipulated Queue message | deny in the limited helper |
| Normal Worker processes a valid Job | allow |
| Shared `aria_worker` credential is fully compromised | residual cross-tenant risk |

**Risk ID:** `WORKER-CROSS-TENANT-001`

**Threat:** compromise of the shared `aria_worker` credential.

**Impact:** potential cross-tenant Job execution and data-access capability.

**Mitigations:** narrow helper, strict Job/Outbox consistency, least privilege, runtime isolation,
secret protection and operational monitoring.

**Residual risk:** the shared Worker remains trusted across Tenants.

**Status:** OPEN — documented, not eliminated. This is not Production risk acceptance.

## Non-goals

Real Provider calls, Usage records, customer content, public API, hosted activation and product
promotion remain prohibited. Synthetic rerun before a durable checkpoint does not authorize real
Provider reinvocation.

Signed delivery capability and Tenant-bound Worker credentials remain deferred to a separate
security review before any real/customer/hosted activation.
