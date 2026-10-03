# Development Record: 0058 — Scope Version Snapshot

- **Status:** COMPLETE
- **Increment:** S1-K05
- **Source sync date:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Freeze the exact current and ready Scope Draft into a tenant-scoped, immutable and traceable Scope
Version. The increment includes versioned canonical JSON hashing, idempotent create semantics,
atomic version allocation, semantic duplicate rejection, summary/detail read APIs and safe
observability. Share and Approval remain excluded.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K05; synchronized 2026-09-12
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Scope Version fields and immutability; synchronized 2026-09-12
- [Canonical API Contract](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — create/list/detail routes; synchronized 2026-09-12
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Member freeze/read and safe tenant boundary; synchronized 2026-09-12
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-07-05 immutable shared/approved versions; synchronized 2026-09-12
- [AI Workflow Specification](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-05 freeze after save; synchronized 2026-09-12
- [Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security) — grants and RLS as independent controls; reviewed 2026-09-12
- Owner-approved K05 refinements dated 2026-09-12
- [ADR-045](../../adr/ADR-045-scope-version-snapshot.md)

Drive documents remain canonical; this record is the developer-facing K05 implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-5801 | Backlog K05; Data Dictionary 14 | `scope_versions` model and Alembic `0018` | TC-5801, TC-5813 |
| REQ-5802 | K05 freeze refinement | Current Draft + current Context + CAS ordering | TC-5802, TC-5803 |
| REQ-5803 | K02 and K05 refinement | Readiness evaluation; `CRITICAL_GAPS_OPEN` | TC-5804 |
| REQ-5804 | Hash refinement | `scope_snapshot_canonicalization_v1`; full-data SHA-256 | TC-5805, TC-5806 |
| REQ-5805 | Duplicate refinement | Latest-hash comparison and `SCOPE_VERSION_UNCHANGED` | TC-5807 |
| REQ-5806 | Idempotency refinement | 24-hour shared reservation; precedence before duplicate check | TC-5808, TC-5809 |
| REQ-5807 | Version allocation refinement | Project lock and unique strictly increasing number | TC-5810 |
| REQ-5808 | Payload/lifecycle refinement | DB trigger protects snapshot; status is separate projection | TC-5811 |
| REQ-5809 | API/Access contracts | Create/list/detail, active Membership, safe 404, no mutation route | TC-5812, TC-5813 |
| REQ-5810 | Security/observability | RLS/revokes, tenant-scoped queries and content-safe events | TC-5814, TC-5815 |

## Changes

- Added the provider/framework-neutral Scope Version Domain and canonicalization/hash functions.
- Added Application ports/service for exact Draft freeze, readiness, idempotency and reads.
- Added SQLAlchemy persistence, atomic Project-lock allocation and migration `0018_scope_versions`.
- Added immutable-payload/delete protection while leaving lifecycle `status` separately controlled.
- Added create/list/detail FastAPI routes and synchronized OpenAPI contracts.
- Added operational and Product Analytics events without Scope content, trace or full hash.
- Added Domain, Application, API, contract and real PostgreSQL integration coverage.

## Structure Preservation

- K01 `scope_content_schema_v1` remains the only snapshot payload schema; K05 deep-copies it rather
  than introducing another Scope representation.
- K02 remains the pure readiness authority; K05 consumes its decision without persisting another
  readiness field or score.
- Domain uses only standard-library and Domain dependencies. FastAPI, SQLAlchemy, PostgreSQL locks,
  RLS and idempotency persistence remain outside Domain.
- Existing 24-hour idempotency records and tenant-context dependency are reused; no new deployable,
  Provider, Queue or direct Data API surface is introduced.
- M010 policy selection remains structurally preserved: the new public-schema table is RLS-enabled
  and fail-closed to public/Data API roles until that approved batch.
- Share, Approval and post-create status transitions remain outside K05.

## Senior Review

**Status:** PASS.

- Corrected the infrastructure boundary so Scope Version persistence does not import a private
  mapper from the Draft repository.
- Normalized idempotency timestamps to UTC and mapped shared idempotency storage failures to the
  declared Scope Version Infrastructure error.
- Corrected OpenAPI detail composition to avoid conflicting `additionalProperties:false` schemas.
- Verified project-first row locking serializes concurrent freeze commands and duplicate detection
  happens only after exact idempotency replay/conflict handling.
- Verified snapshot hash covers lineage trace and logs exclude snapshot, trace and full hash.

## Verification

Focused and complete repository Domain/Application/API/contract/PostgreSQL tests, lint, typecheck,
build, validation, secret scan and diff checks are passing. Evidence is recorded in
[test-report.md](./test-report.md).

## Remaining Risks

- Approval records, status transitions and share-link behavior remain separate unimplemented
  stories by contract.
- Real hosted Supabase migration evidence remains deployment evidence; K05 currently uses local
  PostgreSQL 16 integration evidence.

## Assumptions and Clarifications

- The owner-approved K05 refinement freezes CAS/readiness ordering, canonicalization/hash,
  idempotency precedence, duplicate rejection, lifecycle projection, API exposure and logging.
- Cursor pagination and the 24-hour idempotency window reuse already approved repository-wide API
  and idempotency contracts.
- No direct Data API grant or pre-M010 policy was invented.

**Unapproved assumptions:** None
