# Development Record: 0048 — Gap Domain

- **Status:** COMPLETE
- **Increment:** S1-J01
- **Source sync date:** 2026-09-07
- [Test report](./test-report.md)

## Scope

Implement the accepted Gap Domain/Data contract, logical M006 `gaps` table, tenant-safe repository
boundary, H01-compatible provenance validation and safe creation telemetry. Gap Detection,
Clarification, resolution commands, public API and UI remain deferred.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J01
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap baseline
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03 vocabulary
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — Gap DDL baseline
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — M006
- [ADR-035 — Gap Domain](../../adr/ADR-035-gap-domain-contract.md)
- Owner-approved J01 contract and refinements dated 2026-09-07.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4801 | J01 owner contract: exact canonical vocabulary and `open` default | `apps/api/app/modules/gaps/domain/gap.py`; `apps/api/app/modules/gaps/infrastructure/models.py` | TC-4801 |
| REQ-4802 | J01 owner contract; Migration Plan M006: exact Gap data contract | `apps/api/migrations/versions/0014_gaps.py`; `apps/api/migrations/env.py` | TC-4802 |
| REQ-4803 | H01 provenance contract; J01 empty-provenance clarification | `apps/api/app/modules/gaps/application/gap_service.py`; `apps/api/app/modules/gaps/infrastructure/repository.py` | TC-4803 |
| REQ-4804 | J01 tenant consistency, RESTRICT, hard-delete and private-table guardrails | `apps/api/migrations/versions/0014_gaps.py`; `apps/api/app/modules/gaps/infrastructure/models.py` | TC-4804 |
| REQ-4805 | J01 `resolved_at`/dismissed refinement and PostgreSQL-owned timestamps | `apps/api/app/modules/gaps/domain/gap.py`; `apps/api/migrations/versions/0014_gaps.py` | TC-4805 |
| REQ-4806 | J01-only scope and formal supersede/deferrals | `docs/adr/ADR-035-gap-domain-contract.md`; `docs/architecture/data-model.md`; `scripts/test/gap-domain-contract.test.js` | TC-4806 |
| REQ-4807 | J01 safe structured `gap.created` event | `apps/api/app/modules/gaps/application/gap_service.py`; `packages/observability/src/aria_observability/logging.py` | TC-4807 |
| REQ-4808 | AGENTS quality and documentation gates | `apps/api/tests/test_gap_domain.py`; `apps/api/tests/test_gap_application.py`; `apps/api/tests/test_gap_postgres.py`; this record and `test-report.md` | TC-4808 |

## Assumptions and Clarifications

- The owner-approved 2026-09-07 contract resolves the source conflicts. ADR-035 records every
  superseded field/vocabulary and every J02/J03 deferral.
- The one-way `resolved_at` invariant follows the approved nullable schema: a non-null value is
  legal only for `resolved`; J01 does not invent a rule requiring every resolved row to have it.
- Current Supabase guidance was rechecked on 2026-09-07: a public-schema table requires explicit
  RLS/grant treatment even when the application currently uses a direct server connection. The
  Gap table therefore remains fail-closed to Data API roles.

**Unapproved assumptions:** None

## Changes

- Added logical M006 migration `0014_gaps` with the exact 11 approved columns, canonical checks,
  tenant-safe composite Project FK, RESTRICT delete behavior, tenant-leading index, RLS, explicit
  grant revocation and PostgreSQL-managed `updated_at`.
- Added a framework-free Gap Domain model and H01-compatible Source Reference value object.
- Added an Application port/use case and SQLAlchemy adapter that validate non-empty provenance as
  same-account, same-project, same-source-version and `ready` before persistence. Empty provenance
  remains valid.
- Added safe `gap.created` telemetry and the corresponding observability allowlist fields. No Gap
  content, Source Reference, canonical text or raw text can pass that allowlist.
- Added contract, Domain, Application and real PostgreSQL coverage, including full migration
  downgrade/re-upgrade and full API regression evidence.
- Updated the developer-facing data-model mirror and ADR index. No public endpoint or UI surface
  was added.

## Structure Preservation

- Gap code remains inside the modular-monolith API module.
- Domain imports no framework/infrastructure package; Application depends on ports; SQLAlchemy is
  isolated in Infrastructure.
- The existing Alembic chain is extended from `0013_requirement_crud`; no prior migration is
  rewritten.
- The canonical public API contract is unchanged because J01 authorizes no Gap endpoint.
- No public API, UI, Provider, Queue, Job, Outbox or new deployable is introduced.

## Senior Review

- **Status:** PASS.
- Confirmed the migration contains only the approved fields and that composite referential
  integrity prevents cross-tenant Project linkage at the database boundary.
- Confirmed `RESTRICT`, RLS and revoked Data API grants are exercised on PostgreSQL 16, not only
  inspected as source text.
- Confirmed Source Reference validation is tenant-scoped and requires a ready Source Version;
  bounded offsets cannot exceed canonical text.
- Confirmed `dismissed` and `resolved` remain distinct and that J02 detection/linkage plus J03
  resolution/Clarification behavior did not leak into J01.
- Found and fixed three implementation/test issues during review: missing safe Gap fields in the
  structured-logging allowlist, a formatter-sensitive contract assertion, and an asyncpg fixture
  timestamp type mismatch. All suites passed after the fixes.
- No blocking defect, unapproved behavior, hidden default or structure violation remains.

## Verification

- Contract: 4/4 PASS.
- Focused Domain/Application: 16/16 PASS.
- Gap PostgreSQL integration: 11/11 PASS.
- Full API suite with PostgreSQL integration enabled: 374/374 PASS.
- Monorepo lint, typecheck and production build: PASS.
- Final `npm test`, `npm run validate`, secret scan and diff check: PASS; detailed commands and
  results are in the linked test report.

## Remaining Risks

- J02 detection/evidence/linkage and J03 Clarification/resolution contracts remain explicitly
  deferred; their absence is not a J01 defect.
- Supabase-hosted migration execution is not part of this local increment. The migration and
  permissions were verified against PostgreSQL 16, while current Supabase RLS/grant guidance was
  reviewed separately.
