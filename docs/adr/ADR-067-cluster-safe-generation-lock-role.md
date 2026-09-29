# ADR-067: Cluster-safe Generation Lock Owner Role

- **Status:** Accepted — owner-approved limited migration-safety remediation 2026-09-28
- **Date:** 2026-09-28
- **Extends:** ADR-008 and ADR-064

## Problem

Migration 0030 creates `aria_generation_lock_owner` as though PostgreSQL Roles were
database-local. Roles are cluster-global, so a full migration chain on a second empty database in
the same cluster fails with `DuplicateObject` even when the existing Role has exactly the approved
least-privilege attributes. An unconditional downgrade `DROP ROLE` can likewise disrupt or fail
when another database in the cluster still uses that Role.

The canonical migration plan requires the full chain to pass from an empty database and requires a
safe rollback or recovery path. This remediation must not expand the Role, Worker, helper, RLS or
tenant contracts accepted in ADR-064.

## Decision

Migration 0030 treats `aria_generation_lock_owner` as a cluster-global prerequisite:

1. If the Role does not exist, migration 0030 creates it with the exact ADR-064 attributes:
   `NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`.
2. If the Role already exists, migration 0030 accepts it only when every one of those attributes
   matches. Any mismatch raises an exception before the database-local schema, grants, policies or
   functions are created. The migration does not silently alter or normalize an existing Role.
3. Database-local objects and privileges remain unchanged from ADR-064.
4. Downgrade removes the database-local functions, policies, grants and schema. It drops the Role
   only when no dependency in another database or shared catalog still references it; otherwise the
   Role is preserved for that other database. The last downgraded database removes the now-unused
   Role.

The migration uses only fixed SQL for the fixed Role name. It accepts no arbitrary identifier,
relation or SQL fragment.

## Consequences

- Multiple empty databases can run the complete migration chain in one PostgreSQL cluster.
- A pre-created elevated or otherwise incompatible Role fails closed instead of being trusted.
- Downgrading one database cannot remove the owner Role from another migrated database.
- Migration 0030 is amended before merge because a later revision cannot repair a failure that
  prevents 0030 itself from completing.
- No public API, runtime behavior, Role capability, Worker credential or RLS policy changes.

## Verification contract

- Static contract test proves conditional creation, exact attribute validation and shared-dependency
  downgrade handling.
- In an isolated PostgreSQL 16 cluster, migrate two empty databases to head sequentially.
- Verify the Role attributes and both databases' helper functions.
- Downgrade one database and prove the Role and the other database's functions remain usable.
- Downgrade the last database and prove the dedicated Role is removed.
- Pre-create one incompatible Role attribute in an isolated cluster and prove migration 0030 fails
  closed.

## Sources

- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — empty-database full-chain, per-migration rollback/recovery and migration-lock requirements; reread 2026-09-28.
- [ADR-008](ADR-008-alembic-migration-strategy.md).
- [ADR-064](ADR-064-generation-input-row-lock-privileges.md).
- Owner-approved limited cluster-idempotent/fail-closed remediation, 2026-09-28.
