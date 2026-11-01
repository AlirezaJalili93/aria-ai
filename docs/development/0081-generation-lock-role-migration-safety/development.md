# Development Record: 0081 Generation Lock Role Migration Safety

- **Status:** COMPLETE — cluster-global Role migration gate passed
- **Increment ID:** `0081-generation-lock-role-migration-safety`
- **Source sync date:** 2026-09-28
- [Test report](./test-report.md)

## Scope

Make migration 0030 safe for multiple databases in one PostgreSQL cluster by conditionally creating
and strictly validating its dedicated cluster-global Role, and by preserving that Role during a
database downgrade while another database still depends on it. Runtime privileges, helpers, RLS,
Worker scope and public behavior remain unchanged.

## Source Documents

- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — fresh-chain, rollback/recovery and deployment migration controls; reread 2026-09-28.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — migration-from-empty quality gate; reread 2026-09-28.
- [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md), [ADR-064](../../adr/ADR-064-generation-input-row-lock-privileges.md), [ADR-067](../../adr/ADR-067-cluster-safe-generation-lock-role.md).
- Owner-approved limited migration-safety remediation, 2026-09-28.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-8101 | Migration Plan sections 1, 16 and 25; owner approval | Conditional Role creation in migration 0030 | TC-8101 |
| REQ-8102 | ADR-064/067; owner approval | Exact least-privilege attribute validation and fail-closed mismatch | TC-8102 |
| REQ-8103 | Migration Plan sections 16 and 19; ADR-067 | Dependency-aware downgrade Role cleanup | TC-8103 |
| REQ-8104 | ADR-064/067 | No privilege, helper, RLS or runtime expansion | TC-8104 |

## Assumptions and Clarifications

- PostgreSQL Roles are cluster-global while schemas, functions, policies and table grants are
  database-local; the approved remediation explicitly accounts for that boundary.
- Migration 0030 must be amended before merge because a later revision cannot repair an earlier
  duplicate-Role failure.
- **Unapproved assumptions:** None

## Changes

- Accepted ADR-067 and linked it from the ADR index.
- Changed migration 0030 to create `aria_generation_lock_owner` only when absent and to validate
  every approved least-privilege Role attribute when it already exists.
- Added dependency-aware downgrade cleanup: database-local objects are always removed, while the
  cluster-global Role remains until no other database/shared dependency references it.
- Added a static contract test and an isolated PostgreSQL 16 gate covering two fresh databases,
  ordered downgrade behavior and a deliberately incompatible pre-existing Role.
- Added `npm run test:generation-lock-role-migration` and documented the refined migration behavior.

## Architecture and Design Decisions

See ADR-067. Existing Role attributes are validated, never silently altered. Downgrade removes the
Role only when it has no remaining dependency outside the current database.

## Structure Preservation

PASS. No module boundary, public contract, privilege set, helper signature, RLS policy or
deployment topology changed. Migration 0030's database-local schema, grants, policies and
functions remain byte-for-byte equivalent in intent; only cluster-global Role lifecycle handling
changed. No new deployable, dependency or runtime code path was added.

## Senior Review

- **Least privilege:** PASS. Existing Roles are accepted only when all seven frozen security
  attributes are false; the migration never alters an incompatible Role into compliance.
- **Failure atomicity:** PASS. Attribute validation occurs before database-local 0030 DDL in the
  same transactional migration, and the incompatible-role test leaves no `aria_internal` schema.
- **Cluster safety:** PASS. Two fresh databases reached head in one isolated cluster. Downgrading
  the first preserved the shared Role and the other database's helpers; downgrading the last
  removed the unused Role.
- **Scope:** PASS. No existing Worker raw SELECT/RLS behavior or generation helper capability was
  redesigned.

## Verification

See [test report](./test-report.md). Contract, isolated PostgreSQL migration, lint, typecheck,
build, full repository test and documentation/architecture validation gates passed.

## Remaining Risks

- The dedicated Role is intentionally retained if any dependency outside the downgraded database
  remains. Operational removal of an unexpected external dependency requires explicit DBA review;
  downgrade does not force-drop or reassign shared objects.
- This increment does not alter the deferred shared Worker credential/raw SELECT architecture
  concern recorded by ADR-064.
