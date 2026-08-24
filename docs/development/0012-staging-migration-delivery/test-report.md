# Test Report: Staging Migration Delivery

- Increment ID: `0012-staging-migration-delivery`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Local OS: Windows; clean branch from `origin/main`.
- GitHub Actions: Ubuntu runner, Python and uv versions pinned by repository configuration.
- Supabase Staging: `aria-ai-staging` (`hqgfqlvfwflbazsuhazs`), Frankfurt
  `eu-central-1`, PostgreSQL 17, credential values redacted.
- Railway Staging API: Frankfurt/EU staging service following GitHub `main`.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1201 | Contract | Inspect Staging migration workflow triggers, permissions, Environment, and concurrency | Only `main` may mutate Staging; runs serialize; token permissions are read-only |
| TC-1202 | Contract | Inspect credential and advisory-lock contract | Credential exists only as an Environment secret; runner locks/unlocks safely and logs no DSN |
| TC-1203 | CI/Integration | Run repository quality gate with real PostgreSQL migration tests | M000/M001 fresh upgrade, downgrade/recovery, and re-upgrade tests pass |
| TC-1204 | Static/Integration | Verify M001 RLS and no policy/Data API grants | All three tables enable RLS; deferred M010 behavior is not invented |
| TC-1205 | Configuration/Security | Read back GitHub `staging` Environment metadata | Only `main` is allowed and only the expected secret name exists; no value is returned |
| TC-1206 | Configuration | Read back Railway API source settings | Auto Deploy is enabled; source remains `main` and existing Watch Paths are preserved |
| TC-1207 | Repository gate | Run `npm test` and `npm run validate` with this complete record | Both mandatory gates pass |
| TC-1208 | Security | Scan locked dependencies and publishable files | No blocking vulnerability or committed credential is detected |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-1201 | `npm run test:ci` | 31/31 passed, including four Staging migration CI/CD contract tests | PASS |
| TC-1202 | Run `scripts/db/migrate.py` twice on PostgreSQL 18; hold the same advisory lock in a separate session and run again | First run applied M000/M001; second verified exact `0001_identity_projection` with duration; collision returned exit 1 and `MigrationLockUnavailable` | PASS |
| TC-1203 | `npm run quality` with local `TEST_DATABASE_URL`/`DATABASE_URL` after locked installs | Lint/type-check, 126 tests, Web/API/Worker builds, and architecture checks passed after final record completion | PASS |
| TC-1204 | Existing M001 contract tests plus 71 API tests on real PostgreSQL | Three M001 tables, constraints/indexes, RLS enablement, no M010 policy/grant, upgrade/downgrade/re-upgrade, rollback, idempotency, and concurrency coverage passed | PASS |
| TC-1205 | GitHub Environment/secret/policy API readback | `staging`; one encrypted secret name `STAGING_DATABASE_URL`; one exact branch policy `main`; no secret value returned | PASS |
| TC-1206 | Railway Settings DOM readback after authorized Enable action | `Auto deploys when pushed to GitHub`; connected branch remains `main`; API service remains Online | PASS |
| TC-1207 | `npm test`; `npm run validate` | 126/126 tests passed; 22/22 architecture/content checks passed | PASS |
| TC-1208 | `npm run scan:dependencies`; `npm run scan:secrets` | npm/API/Worker scans found no blocking vulnerability; secret scan inspected 172 publishable text files | PASS |

## Failures and Corrections

1. The first real migration run succeeded but its completion/duration line was absent because
   Alembic logging configuration disabled the runner logger. A dedicated safe logger is restored
   after Alembic; repeat execution logged revision and `duration_ms`.
2. The first lock-collision attempt missed the timing window after the external session released.
   The test was repeated with a longer bounded lock hold and correctly returned exit code 1.
3. The first full quality run reached 126 passing tests but Web build failed because the new worktree
   did not yet contain a complete lockfile installation. `npm ci` installed 350 locked packages with
   zero audit vulnerabilities; the build passed on rerun.
4. The second full quality run correctly failed only because this record was still PENDING while
   hosted evidence could not exist pre-merge. Scope was split truthfully: this implementation record
   completes locally, and post-merge hosted evidence is owned by increment 0013. No validator was
   bypassed or weakened.
5. The first local dependency-scan invocation could not locate `uv` in the new worktree. Re-running
   with the repository's pinned `UV_PATH` completed all npm/API/Worker audits successfully.

## Final Status

**Final status:** PASS
