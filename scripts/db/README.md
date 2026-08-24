# Controlled database migrations

`migrate.py` is the CI/CD entry point accepted by ADR-008. It runs the repository-owned Alembic
chain while holding a PostgreSQL advisory lock, then verifies that the database revision exactly
matches the single repository head.

The command requires `DATABASE_URL` at runtime and never prints the value:

```text
uv run --project apps/api python scripts/db/migrate.py
```

Shared Staging execution is owned by `.github/workflows/staging-migrations.yml`. The workflow reads
the URL from the `staging` GitHub Environment secret `STAGING_DATABASE_URL`; application startup,
local ad-hoc execution, and Supabase Dashboard schema mutation are not deployment paths.
