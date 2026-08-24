# Migrations

Alembic is the accepted migration owner under ADR-008. `DATABASE_URL` is required at execution and
is never stored in this directory.

```text
0000_extensions → 0001_identity_projection → 0001_identity_access_hardening
```

M001 creates `accounts`, `profiles`, and `account_memberships` and enables RLS with no policy or Data
API access, so the public schema is deny-by-default for non-owner roles. The follow-up M001
hardening revision enables RLS on Alembic's version table, revokes provider-created `anon` and
`authenticated` privileges from the current tables when those roles exist, and removes matching
default privileges owned by the migration role. Supabase also has provider-owned
`supabase_admin` defaults that the migration role cannot modify. Until the documented M010 policy
step, every new Aria public-table migration must therefore explicitly revoke current
`anon`/`authenticated` table privileges. Applied shared-environment revisions are immutable.
