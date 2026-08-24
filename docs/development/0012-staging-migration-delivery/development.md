# Development Record: Staging Migration Delivery

- Increment ID: `0012-staging-migration-delivery`
- Date: 2026-08-24
- Owner: Backend / Platform
- Related plan/issue: S1-B02 Account Bootstrap staging delivery
- [Test report](./test-report.md)

## Scope

Create and verify the controlled, serialized, main-only CI/CD path that will deliver the
already-approved M000/M001 Alembic chain to the independent Supabase Staging database after merge.
This implementation increment includes the protected GitHub Environment, credential binding,
database advisory lock, exact-revision assertion, safe duration evidence, and failure artifact. The
post-merge hosted execution and database/API readback are recorded truthfully in the next operational
evidence increment. This increment does not add tables beyond M000/M001, select the deferred M010
tenant-policy model, grant Data API access, seed data, or change Production.

## Source Documents

- User approval on 2026-08-24 to enable Railway API Auto Deploy and create/run the controlled
  Supabase Staging M000/M001 CI/CD path.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — FINAL; synced 2026-08-24; sections 1, 16, 19–21, and 25.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — FINAL; synced 2026-08-24; S1-A03, S1-B02, and Definition of Done.
- [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md) — accepted Alembic ownership and CI/CD execution boundary.
- [Documentation-driven development policy](../../governance/document-driven-development.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-057 | Migration Plan §§1,20: no manual shared-schema mutation; merge main deploys/migrates Staging | `.github/workflows/staging-migrations.yml` | TC-1201, TC-1205 |
| REQ-058 | Migration Plan §§20–21: single-run migration lock and duration evidence | `scripts/db/migrate.py`; workflow concurrency | TC-1202 |
| REQ-059 | ADR-008: Alembic remains migration owner and credential is runtime-only | workflow secret binding; existing `apps/api/migrations/**` | TC-1202, TC-1203 |
| REQ-060 | Migration Plan §§16,25: fresh-chain and exact applied-revision verification | PR CI PostgreSQL service; runner revision assertion | TC-1202, TC-1203, TC-1204 |
| REQ-061 | M001/ADR-008: M001 tables enable RLS without selecting M010 policies or Data API grants | existing immutable M001; contract and PostgreSQL integration tests | TC-1203, TC-1204 |
| REQ-062 | User approval: Staging mutation is protected and Railway API follows future `main` pushes | GitHub `staging` Environment; Railway Auto Deploy | TC-1205, TC-1206 |

## Assumptions and Clarifications

- The user explicitly approved both the Railway Auto Deploy action and the controlled Supabase
  Staging migration-delivery path on 2026-08-24.
- `staging` is an execution Environment boundary; the database credential is named
  `STAGING_DATABASE_URL` to distinguish it from runtime and Production credentials.

**Unapproved assumptions:** None

## Changes

- Added `.github/workflows/staging-migrations.yml`: `main`-only push/manual entry, read-only token,
  non-cancelling concurrency group, protected Environment secret, locked dependency installation,
  exact source SHA evidence, bounded execution, and always-uploaded log artifact.
- Added `scripts/db/migrate.py`: provider-neutral Alembic execution under a PostgreSQL advisory lock,
  fail-fast collision behavior, exact single-head verification, credential-safe logging, duration
  evidence, and guaranteed connection disposal/session lock release.
- Added `scripts/db/README.md` and four CI contract tests.
- Added the migration runner to API lint, type-check, and build surfaces in `package.json`.
- Created GitHub Environment `staging`, stored only the encrypted secret name
  `STAGING_DATABASE_URL`, and limited deployment policy to the exact `main` branch.
- Enabled Railway API Auto Deploy while retaining `main` and the existing API Watch Paths.

## Architecture and Design Decisions

- No new ADR is required: this increment executes ADR-008 without changing migration ownership,
  deployables, module boundaries, database provider abstraction, or schema structure.
- GitHub concurrency serializes intended runs; the PostgreSQL session-level advisory lock is the
  database-side last line of defense against a second executor outside that queue.
- The runner verifies `alembic_version` against the repository's one allowed head before reporting
  success. Application startup remains migration-free.
- Supabase CLI and Dashboard DDL are intentionally absent because Alembic is the accepted owner.

## Structure Preservation

- Existing Alembic revisions and the single chain under `apps/api/migrations/versions` are unchanged.
- The canonical `/scripts/db/` structure is activated without moving API migration configuration.
- Modular-monolith Domain/Application/Infrastructure boundaries and all public contracts are
  unchanged; no service, endpoint, table, field, grant, policy, seed, or dependency was introduced.
- Existing CI remains the pull-request fresh-database gate; the new workflow is a separate
  post-merge Staging delivery boundary.

## Senior Review

- **HIGH — corrected:** Alembic's `fileConfig` disabled the runner logger, which suppressed the
  required completion/duration record. The runner now restores a dedicated credential-safe logger
  after Alembic configuration; the second real-PostgreSQL execution recorded revision and duration.
- **HIGH — verified:** an independently-held advisory lock caused fail-fast exit code 1 with only
  `MigrationLockUnavailable`; no concurrent upgrade ran and no credential was emitted.
- **MEDIUM — corrected:** the first implementation left the operational runner outside lint,
  type-check, and compile surfaces. All three mandatory API quality scripts now include `scripts/db`.
- **MEDIUM — corrected:** failure evidence was initially created only in the migration step. Evidence
  initialization now precedes secret/dependency checks, so `if: always()` can preserve a source-SHA
  artifact for earlier failures too.
- **LOW — verified:** Environment readback reports one secret name and one exact `main` branch policy;
  values were never displayed, written to disk, shell history, repository files, or logs.
- No actionable senior-review finding remains.

## Verification

The local controlled runner applied M000/M001 to real PostgreSQL, passed idempotent re-execution,
verified exact head, and rejected a concurrent lock holder. Repository contract, API integration,
lint, type-check, and build gates pass. See the linked test report for commands and results.
Dependency and publishable-file secret scans also pass with no blocking finding.

## Remaining Risks

- The first hosted readback exposed implicit Supabase Data API grants and RLS-disabled
  `public.alembic_version`. Increment 0013 owns the immutable hardening revision; increment 0014 then
  records final migration/table/RLS/advisor readback and Railway health smoke before hosted delivery
  is reported complete.
