# Development Record: 0043 — Requirement Domain

- **Status:** COMPLETE
- **Increment:** S1-I01
- **Source sync date:** 2026-09-06
- [Test report](./test-report.md)

## Scope

Implement the approved Requirement Domain/Data contract, Application persistence boundary,
tenant-safe PostgreSQL repository and logical M005 migration. Generation, deduplication, lifecycle
commands, HTTP, UI, evaluation and `acceptance_note` remain outside I01.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I01
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Requirements
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — §6
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — M005
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — §13 and deferred I03 surface
- [Access Control Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — backend tenant authorization
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — Requirement and tenant tests
- [ADR-030 — Requirement Domain and Provenance Contract](../../adr/ADR-030-requirement-domain-contract.md)
- Owner clarification dated 2026-09-06 approving the exact I01 contract.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4301 | S1-I01; owner contract | Requirement Domain entity and exact category/priority/status/creator vocabularies | TC-4301 |
| REQ-4302 | Owner contract; ADR-030 | Integer Context Version `1..Project.current_context_version`; no Context Version entity | TC-4302, TC-4305 |
| REQ-4303 | Data Dictionary; owner supersede | Mandatory `title+description`; old `content` and `context_version_id` absent | TC-4301, TC-4303 |
| REQ-4304 | S1-I01; H01 SourceRef contract | JSON array provenance with ready same-tenant Source/Version and offset validation | TC-4302, TC-4305 |
| REQ-4305 | Owner contract; Migration Plan | Restrictive Account/Project/Creator FKs, composite tenant link, RLS and fail-closed Data API | TC-4303, TC-4304 |
| REQ-4306 | Owner logging guardrail | Identifier-only `requirement.created`; no title, description or source refs | TC-4302, TC-4305 |
| REQ-4307 | Owner scope decision | No dedupe/merge/API/UI/generation/acceptance note/restore in I01 | TC-4306 |

## Assumptions and Clarifications

- Title and Description are not normalized and no minimum content length is invented in I01.
- Priority and category have no database default; callers must provide canonical values explicitly.
- `removed` is represented but no transition, restore or hard-delete operation is exposed.
- `acceptance_note` remains deferred to S1-I03 despite its future API contract.
- **Unapproved assumptions:** None

## Changes

- Added a framework-free Requirement Domain entity with the six canonical categories, explicit
  priority, four-state lifecycle, creator rule, nullable bounded confidence and H01-compatible
  Source Reference value object.
- Added Application ports and `PersistRequirementUseCase`. Persistence locks and resolves the
  same-tenant active Project, rejects missing/future Context Versions, validates every ready Source
  Version and offset, commits once, then emits identifier-only `requirement.created`.
- Added SQLAlchemy model/repository/UoW and `0011_requirements`. M005 supplies mandatory
  title/description/priority, JSON-array provenance, restrictive FKs, composite tenant protection,
  tenant-first indexes, database-owned `updated_at`, RLS and explicit Data API revocation.
- Added Domain, Application, contract and real PostgreSQL coverage, including migration recovery,
  cross-tenant rejection, provenance validation and log-content exclusion.
- Added ADR-030 and synchronized the architecture, module and migration mirrors.

## Structure Preservation

- Preserved `Presentation → Application → Domain` and Infrastructure-implements-Port dependency
  direction. Requirement Domain imports no framework, SQLAlchemy, Supabase or observability code.
- Kept Requirements as a module in the documented modular monolith. No deployable, provider,
  external integration, API route or UI surface was added.
- Context is read only through the Requirement persistence adapter for version/provenance
  validation; no cross-module write was introduced.
- Preserved existing H01 provenance semantics without moving or changing Context code.

## Senior Review

- **Contract parity:** PASS. The migration and Domain share exact category, priority, status and
  creator vocabularies; deprecated `context_version_id`, `content`, `source_type` and
  `acceptance_note` are absent.
- **Tenant/security:** PASS. Account and composite Project/Account FKs are restrictive, provenance
  queries include Account and Project, soft-deleted Projects are rejected, RLS is enabled and Data
  API roles have zero direct grants.
- **Consistency:** PASS after correction. Project version resolution now takes a row lock so a
  concurrent Project mutation cannot invalidate the create decision within the transaction.
- **Provenance:** PASS. Every non-empty Source Reference resolves to a ready exact Source Version;
  offset references require canonical text and stay within its length.
- **Observability/privacy:** PASS after extending the existing safe-field allowlist with
  `requirement_id`, `priority` and `created_by_type`. Tests prove title, description and source refs
  do not appear in the emitted event.
- **Migration/recovery:** PASS on PostgreSQL 16. Fresh/current upgrade, constraints, trigger,
  downgrade to 0010 and re-upgrade to head all passed.
- **Scope:** PASS. No merge/dedupe, generation, mutation, restore, HTTP, UI, evaluation or
  `acceptance_note` behavior was introduced.

## Verification

- Requirement Domain/Application focused suite: 19 passed.
- Requirement PostgreSQL suite: 15 passed.
- Contract CI suite: 116 passed.
- Complete PostgreSQL-backed API suite: 299 passed with one dependency deprecation warning.
- Eval: 8 passed; Web: 19 passed; Worker: 55 passed.
- Full lint, strict typecheck and build passed for Web, API and Worker.
- Mandatory `npm test` and `npm run validate` final results are recorded in the linked report.

## Remaining Risks

- Title/description normalization and minimum non-empty policy remain intentionally undefined and
  must be resolved by I02/I03 before accepting external input.
- JSONB cannot enforce element-level provenance FKs; all supported persistence must continue
  through the validated Application boundary.
- The optional repository-wide `alembic check` diagnostic reports the pre-existing G05
  `usage_records` table as absent from API-owned SQLAlchemy metadata because its writer model lives
  in the Worker deployable. It reported no Requirement operation; resolving that cross-deployable
  metadata ownership is outside I01 and must not be hidden by an Alembic ignore rule.
- Generation/unsupported classification/merge, lifecycle CRUD and `acceptance_note`, UI, quality
  evaluation and removed-item restoration remain deferred to their approved Stories.
