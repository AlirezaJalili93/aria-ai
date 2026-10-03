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

## Controlled 0086 evaluation prices

`provision_eval_prices.py` inserts only the two owner-frozen Standard-tier Price Versions required
by the isolated 0086 synthetic evaluation. It never reads Provider credentials or makes a Provider
call. The command is idempotent only when existing rows match every frozen field; a missing or
conflicting identity/effective-time row fails and rolls back the whole transaction.

Run it only against the migrated throwaway evaluation PostgreSQL database, using a Platform-owned
credential that can insert into `provider_price_versions`:

```text
DATABASE_URL=<isolated-eval-database>
ARIA_EVAL_DATABASE_CONFIRMED=provision-0086-controlled-eval-prices
uv run --project apps/api python scripts/db/provision_eval_prices.py
```

Neither variable may be committed or printed. This provisioning path does not authorize a paid
Provider invocation; the separate 0086 credential/model/budget preflight remains mandatory.
