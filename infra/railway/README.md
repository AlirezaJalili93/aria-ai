# Railway Staging Configuration

This directory defines the repository-owned deployment contract for the existing API and Worker
deployables. Railway dashboard values remain limited to service linkage, the verified Git branch,
and environment variables or secrets.

## Service mapping

| Service | Config file | Public network | Health contract |
|---|---|---|---|
| `aria-staging-api` | `/infra/railway/api.railway.json` | Railway TLS domain | `/health/ready` |
| `aria-staging-worker` | `/infra/railway/worker.railway.json` | Disabled | Process remains running |

Both services use one replica in Railway EU West Metal (`europe-west4-drams3a`, Amsterdam). The
Supabase project and the separately managed Redis-compatible queue remain in Frankfurt. This is a
staging-only proximity compromise, not a production region decision.

## Required runtime bindings

The dashboard must provide the explicit service values below; Railway injects the listed native
deployment metadata. Values must never be copied into this repository, deployment logs,
screenshots, or development records.

### API

- `APP_ENV=staging`
- `APP_VERSION=0.1.0`
- `LOG_LEVEL=INFO`
- `PUBLIC_APP_URL`
- `API_BASE_URL`
- `DATABASE_URL`
- `QUEUE_BROKER_URL`
- `STORAGE_ENDPOINT`
- `STORAGE_BUCKET=aria-staging-project-content`
- `STORAGE_ACCESS_KEY`
- `STORAGE_SECRET_KEY`
- `AUTH_PROVIDER_URL`
- `AUTH_JWKS_URL`
- `AUTH_AUDIENCE=authenticated`
- Railway-provided `RAILWAY_GIT_COMMIT_SHA` (injected automatically for GitHub-triggered deploys)

### Worker

- `APP_ENV=staging`
- `APP_VERSION=0.1.0`
- `LOG_LEVEL=INFO`
- `DATABASE_URL`
- `QUEUE_BROKER_URL`
- `QUEUE_NAME`
- `QUEUE_VISIBILITY_TIMEOUT_SECONDS`
- `WORKER_CONCURRENCY`
- `STORAGE_ENDPOINT`
- `STORAGE_BUCKET=aria-staging-project-content`
- `STORAGE_ACCESS_KEY`
- `STORAGE_SECRET_KEY`
- Railway-provided `RAILWAY_GIT_COMMIT_SHA` (injected automatically for GitHub-triggered deploys)

Do not create a dashboard `RELEASE_COMMIT_SHA` reference to the Git variable. Railway injects Git
variables only for GitHub-triggered builds/deployments; the tested reference resolved empty during
a manual configuration redeploy. API and Worker map the native Railway value to the
provider-neutral release identity, and the native value takes precedence over a legacy
`RELEASE_COMMIT_SHA` value.

## Hosted verification gate

1. Bind both services to the same GitHub branch and verify the deployed SHA.
2. Keep the Worker private and generate a public Railway domain only for the API.
3. Confirm `/health/live` returns `200` without dependency calls.
4. Confirm `/health/ready` returns `200` only when PostgreSQL and Queue probes both pass.
5. Record service region, deployment SHA, TLS URL, sanitized health responses, and rollback source.
6. Remove the temporary Trial deployment after evidence capture unless an approved budget replaces
   the temporary staging decision.
