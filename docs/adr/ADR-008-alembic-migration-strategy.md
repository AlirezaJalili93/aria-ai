# ADR-008: Alembic Migration Strategy

- Status: Accepted
- Date: 2026-08-22
- Canonical references: Database Migration Execution Plan v1.0, Dependency & Vendor Register v1.0,
  Coding Standards & Engineering Conventions v1.0

## Context

S1-B02 is the first approved Story that persists Identity projection state and therefore activates
the deferred database-migration decision from ADR-004. The canonical Migration Plan specifies
Alembic with SQLAlchemy metadata and explicit SQL for PostgreSQL-specific controls. The final
Dependency Register records Alembic as the critical migration dependency.

## Decision

- Use Alembic 1.19.0 with the repository's pinned SQLAlchemy 2.x and asyncpg stack.
- Keep migration configuration under `apps/api` and revisions under
  `apps/api/migrations/versions`.
- Use deterministic `revision_short_description` filenames and a single revision chain.
- Load the database URL only from runtime environment configuration; never store a credential in
  `alembic.ini` or a migration.
- Write reviewable explicit revisions. PostgreSQL-specific extension, constraint, index, and future
  RLS operations may use explicit SQL where Alembic operations are insufficient.
- Test fresh upgrade, downgrade where safe, and re-upgrade against real PostgreSQL.
- Applied shared-environment revisions are immutable; corrections use a new revision.

## Consequences

Schema history is vendor-portable PostgreSQL migration code and remains owned by the API deployable.
Migration execution is controlled by CI/CD, not application startup or Supabase Dashboard mutation.
M001 enables RLS on its public-schema tables but does not select the future M010 Tenant policy and
grants no Data API access.

## Rejected

- Runtime `create_all`: no reviewable history or controlled rollback.
- Manual Dashboard/SQL changes: creates schema drift and violates the Migration Plan.
- Supabase-specific migration ownership: unnecessarily couples the provider-neutral persistence
  boundary to a hosting vendor.
