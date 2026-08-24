# Development Record: Staging Data API Hardening

- Increment ID: `0013-staging-data-api-hardening`
- Date: 2026-08-24
- Owner: Backend / Platform / Security
- Related plan/issue: S1-B02 hosted security correction
- [Test report](./test-report.md)

## Scope

Correct the hosted security mismatch discovered after M000/M001 delivery without editing an applied
shared revision. Add one forward Alembic revision that enables RLS on the public Alembic version
table, revokes implicit `anon`/`authenticated` privileges from the Identity and version tables, and
removes the same future public-table default privileges when those provider roles exist. This
increment does not select M010 tenant policies, add a public policy/grant, change product schema, or
touch Production.

## Source Documents

- User approval on 2026-08-24 to continue the controlled Supabase Staging migration path and perform
  complete senior review/debugging.
- Hosted Supabase Security Advisor and grant readback on 2026-08-24: RLS-disabled
  `public.alembic_version` plus implicit `anon`/`authenticated` table privileges.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — FINAL; synced 2026-08-24; immutable shared revisions, RLS, security baseline, and forward-fix/recovery.
- [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md) — no Data API grants and applied shared-revision immutability.
- [Documentation-driven development policy](../../governance/document-driven-development.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-063 | ADR-008: applied M001 is immutable; corrections use a new revision | `0001a_identity_projection_access_hardening.py` | TC-1301, TC-1304 |
| REQ-064 | Migration Plan/Advisor: every exposed public table has RLS | hardening revision enables RLS on `public.alembic_version` | TC-1301, TC-1302 |
| REQ-065 | ADR-008: M001 grants no Data API access before M010 policy selection | conditional revoke of existing and default `anon`/`authenticated` table privileges | TC-1301, TC-1302 |
| REQ-066 | Architecture: Alembic remains provider-neutral and local PostgreSQL remains supported | role-existence guard; no Supabase CLI/SDK/service role | TC-1301, TC-1302, TC-1303 |
| REQ-067 | Quality rules: recovery path, complete records, mandatory gates | downgrade/re-upgrade coverage; this record and linked report | TC-1302, TC-1303, TC-1304 |

## Assumptions and Clarifications

- The correction implements the already-accepted no-Data-API-access decision; it introduces no
  product behavior or tenant-policy model.
- Provider roles are detected from `pg_roles`; generic PostgreSQL environments without those roles
  remain valid and receive the provider-neutral RLS correction.

**Unapproved assumptions:** None

## Changes

- Added an immutable forward Alembic revision after `0001_identity_projection`.
- Added contract and real-PostgreSQL coverage for RLS, current grants, default privileges,
  downgrade, and re-upgrade.
- Updated the migration chain README and the previous increment's truthful remaining-risk routing.

## Architecture and Design Decisions

- No ADR change is required: the revision enforces ADR-008 and does not change schema ownership.
- Role-specific statements are conditional capabilities at the infrastructure boundary; there is no
  Supabase dependency, and generic PostgreSQL execution remains unchanged.
- Downgrade restores the prior provider privilege/RLS state only when the roles exist; Production
  rollback remains governed by the documented forward-fix/recovery policy.

## Structure Preservation

- Existing shared revisions `0000_extensions` and `0001_identity_projection` are unchanged.
- The single Alembic chain is preserved; the next semantic M002 remains Projects.
- No table, product field, endpoint, module, deployable, policy, seed, or dependency is added.

## Senior Review

- Hosted finding severity: **HIGH / corrected in code**.
- The revision covers both already-created tables and the owner role's future public-table defaults,
  preventing the same provider behavior from recurring on later migrations before M010.
- The Alembic version table keeps owner access (RLS is not forced), so controlled migration history
  remains writable while Data API roles have no privilege.
- Revision ID length remains within Alembic's existing version column; dynamic role identifiers are
  quoted by PostgreSQL `format(..., %I)` and only sourced from the fixed allowlist query.
- No actionable senior-review finding remains.

## Verification

The complete chain passed against empty real PostgreSQL with simulated provider roles. At head,
`alembic_version` has RLS, the current/default Data API grant counts are zero, and the controlled
runner reports exact revision `0001_identity_access_hardening`. Full repository, dependency, and
secret gates pass. See the linked test report.

## Remaining Risks

- Hosted application and advisor readback occur only after merge through the controlled workflow and
  are owned by increment 0014.
