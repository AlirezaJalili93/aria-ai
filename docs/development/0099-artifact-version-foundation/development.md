# Development Record: 0099 ArtifactVersion Foundation

- Increment ID: `0099-artifact-version-foundation`
- Date: 2026-10-11
- Related domain: Generation / Artifact Persistence
- [Test report](./test-report.md)

## Scope

Introduce the PostgreSQL, Domain and Application Port foundation for one Project website Artifact,
immutable version lineage, private Manifest identity, atomic allocation/finalization and same-Job
recovery. Runtime rendering, public API, Preview and Export remain outside this increment.

## Source Documents

- Owner-approved frozen `0099` contract, 2026-10-11.
- [PRD — Aria AI MVP](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-09-01..10; synchronized 2026-10-11.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Artifact/ArtifactVersion; synchronized 2026-10-11.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — EP-F2 / BE-F2-01..08; synchronized 2026-10-11.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Sprint 3 §14.3; synchronized 2026-10-11.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) and [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit); synchronized 2026-10-11.
- [ADR-086](../../adr/ADR-086-artifact-version-foundation.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9901 | 0099; PRD FR-09 | One website Artifact per Project, created on first allocation | TC-9901, TC-9902 |
| REQ-9902 | 0099; Data Dictionary | Immutable version lineage and exact approved ScopeVersion binding | TC-9901, TC-9903, TC-9906 |
| REQ-9903 | 0099 | Private Manifest reference, exact SHA-256 and schema v1; no AST JSONB | TC-9904, TC-9905 |
| REQ-9904 | 0099; Backlog F2 | Atomic ArtifactVersion + Job + Outbox allocation and Job replay | TC-9901, TC-9902 |
| REQ-9905 | 0099 | Ready-only same-Artifact current pointer and atomic finalization | TC-9904, TC-9905 |
| REQ-9906 | 0099 | Failed finalization rollback and same Job/Version recovery | TC-9904 |
| REQ-9907 | Access Control; 0099 | Composite tenant FKs, RLS and no public Data API grants | TC-9905, TC-9906 |
| REQ-9908 | 0099 | Ready Versions historical/immutable and hard delete prohibited | TC-9906 |

## Assumptions and Clarifications

The owner froze the persistence boundary but intentionally deferred runtime task/event vocabulary,
Renderer execution, concrete object storage, public API, Preview and Export. The foundation accepts
the already-created Job and Outbox value objects so those deferred contracts are not invented here.

**Unapproved assumptions:** None

## Changes

- Added migration `0038_artifact_version_foundation` with composite tenant/ownership FKs, lineage,
  ready-Manifest checks, current-pointer enforcement, immutable history, RLS and restrictive delete.
- Added Generation Domain models and Application allocation/finalization Ports.
- Added a SQLAlchemy repository/UoW implementing atomic allocation, exact replay and finalization.
- Added a private Manifest verification Port and fail-closed service boundary.
- Added unit and real-PostgreSQL tests for concurrency, tenant consistency, rollback and recovery.

## Structure Preservation

- Generation Domain imports no SQLAlchemy, FastAPI, Worker, Renderer or Storage SDK code.
- Infrastructure implements Domain/Application Ports inside the modular monolith.
- Existing Job/Outbox aggregates remain authoritative and are written in the same transaction.
- No endpoint, Worker task, Provider call, Preview host, Export format or new deployable was added.

## Senior Review

- PASS: fixed FK insertion ordering so the Job is flushed before its dependent ArtifactVersion.
- PASS: Project row locking plus DB uniqueness prevents duplicate Artifact/version allocation.
- PASS: DB triggers and composite FKs reject non-ready/wrong-owner current pointers and mutation or
  deletion of ready historical Versions.
- PASS: injected finalization failure rolls back Version/current/Job changes; replay verifies the
  Manifest again and finalizes the same identities.
- PASS: storage verification happens before the DB finalization transaction and invalid manifests
  produce no valid Artifact effect.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- 0100 must define runtime Job/event/task vocabulary, Renderer execution and concrete Storage Port.
- Preview isolation and Export remain independent contracts.
- No Real Provider, Customer Content or Hosted Generation path is authorized by this increment.
- Repository-wide `alembic check` still reports pre-existing metadata gaps for Usage/Provider Price/
  AI Invocation Checkpoint tables and unrelated legacy index/constraint drift. The fresh Migration
  chain and 0099 PostgreSQL tests passed, and no Artifact table drift was reported.

**Final status:** PASS
