# ADR-086 — Artifact and Immutable ArtifactVersion Foundation

- **Status:** Accepted
- **Date:** 2026-10-11
- **Increment:** `0099-artifact-version-foundation`

## Context

The approved Generation contracts require a generated website to become a durable Artifact only
after an approved ScopeVersion has been selected. The canonical PRD, Data Dictionary, Backlog and
Master Plan distinguish the mutable Artifact lifecycle from immutable ArtifactVersion history.
The preceding 0095–0098 increments proved the controlled AST, Renderer, exportability and synthetic
runtime security, but deliberately created no Artifact persistence.

## Decision

- A Project owns at most one `website` Artifact through `UNIQUE(project_id, artifact_type)`.
  The Artifact is created by the first allocation, not with the Project.
- An ArtifactVersion is allocated only for an exact approved ScopeVersion. Version numbers are
  serialized under the Project/Artifact lock and unique within one Artifact. Version one is
  `initial` with no parent; later versions require a parent in the same Artifact.
- The immutable Version stores only a private Manifest reference, SHA-256 of the exact versioned
  Manifest bytes, schema identity `generation_ast_schema/v1`, lineage and generation Job identity.
  The AST is not duplicated into a second JSONB source of truth.
- Allocation creates the Artifact when necessary, the queued ArtifactVersion, the caller-supplied
  Job and its Outbox event in one PostgreSQL transaction. The generation Job is unique and replay
  resolves the same Version instead of allocating another one.
- External Artifact bytes remain behind a verification Port. Finalization first verifies the
  private Manifest reference and exact checksum, then atomically marks the Version ready, advances
  `Artifact.current_version_id`, marks the Artifact ready and succeeds the same Job.
- `current_version_id` is constrained to a ready Version owned by the same Artifact, Account and
  Project. A failed finalization preserves the prior current Version and Job state.
- Ready ArtifactVersion rows are immutable and historical. Artifact lifecycle status and current
  pointer remain mutable only through the guarded Application transaction. Physical deletion of
  Artifact or Version rows is prohibited.
- A DB failure after external upload is recovered with the same Job and ArtifactVersion identity.
  Recovery re-verifies the stable Manifest reference/hash and never requires Provider or Renderer
  reinvocation. Invalid or inaccessible Manifest state fails closed.
- Tenant consistency is enforced with composite foreign keys and RLS is enabled. Public Data API
  roles receive no direct table privileges. Runtime grants and generation execution are deferred
  to the next Generation Service contract.

## Consequences

- PostgreSQL becomes the source of truth for Artifact lifecycle and immutable Version lineage,
  while private object storage remains the source for exact generated files and Manifest bytes.
- The foundation supports initial and later revision allocation without defining a public API,
  Worker task/event vocabulary, rendering execution, Preview hosting or export format.
- 0100 may connect the controlled Renderer and storage implementation to these Ports. Preview and
  export remain separate contracts.

## Sources

- Owner-approved frozen `0099` contract, 2026-10-11.
- [PRD — Aria AI MVP](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-09-01..10; synchronized 2026-10-11.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Artifact and ArtifactVersion baseline; synchronized 2026-10-11.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — EP-F2 / BE-F2-01..08; synchronized 2026-10-11.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Sprint 3 §14.3; synchronized 2026-10-11.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Generation boundary; synchronized 2026-10-11.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership and approved Scope eligibility; synchronized 2026-10-11.
- [ADR-082](ADR-082-generation-component-registry-and-ast.md), [ADR-083](ADR-083-controlled-generation-renderer-proof.md), [ADR-084](ADR-084-controlled-generation-exportability-proof.md) and [ADR-085](ADR-085-generated-runtime-security-review.md).

**Unapproved assumptions:** None
