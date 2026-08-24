# Migrations

Alembic is the accepted migration owner under ADR-008. `DATABASE_URL` is required at execution and
is never stored in this directory.

```text
0000_extensions → 0001_identity_projection
```

M001 creates `accounts`, `profiles`, and `account_memberships` and enables RLS with no policy or Data
API grant, so the public schema is deny-by-default for non-owner roles. Tenant RLS policy selection
remains the documented M010 step. Applied shared-environment revisions are immutable.
