# Test Report: Staging Hosted Evidence

- Increment ID: `0014-staging-hosted-evidence`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Repository: `AlirezaJalili93/aria-ai`, `main` through SHA
  `20046228701c2657cc3c5501871666e105ecb1d2` before this documentation increment.
- Supabase Staging: project `hqgfqlvfwflbazsuhazs`, Frankfurt, PostgreSQL 17.
- Railway Staging API: `https://aria-staging-api-staging.up.railway.app`.
- Verification date: 2026-08-24.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1401 | Hosted CI/CD | Inspect PR #5/#6 checks and main migration runs | Required CI succeeds; main-only serialized migration reaches success and retains evidence |
| TC-1402 | Hosted database | Read Alembic version after PR #6 migration | Exact head is `0001_identity_access_hardening` |
| TC-1403 | Hosted security | Inspect RLS, current grants, policies, default ACL ownership, and Supabase advisors | Four public tables have RLS; current Data API grants are zero; no blocking advisor ERROR; provider defaults are truthfully recorded |
| TC-1404 | Runtime contract/Hosted preflight | Verify native Git SHA precedence and call existing `/health/live` and `/health/ready` | API/Worker prefer valid native SHA; existing endpoints return HTTP 200 with internal readiness checks; post-merge exact-SHA acceptance is routed to 0015 |
| TC-1405 | Repository gate | Run `npm test`, `npm run validate`, and patch hygiene | Mandatory gates and documentation convention pass |

## Execution Results

| ID | Command or evidence | Actual result | Status |
|---|---|---|---|
| TC-1401 | PR #5; migration run `32722298757`; PR #6; migration run `32723496437`; main CI `32723496441` | Both PRs merged; migration runs and main Quality/Security jobs succeeded; migration evidence artifacts retained | PASS |
| TC-1402 | Controlled workflow output and direct `public.alembic_version` readback | Exact revision `0001_identity_access_hardening` | PASS |
| TC-1403 | Supabase catalog/advisor readback | RLS=true on `accounts`, `profiles`, `account_memberships`, `alembic_version`; zero current `anon`/`authenticated` grants; no policies; no advisor ERROR; four expected no-policy INFO and two unused-index INFO; provider-owned `supabase_admin` defaults remain as documented risk | PASS |
| TC-1404 | API/Worker bootstrap tests; Railway redeploy; hosted GET requests | Native-over-legacy mapping tests passed in both deployables; existing live/ready returned HTTP 200 and configuration/database/queue passed; stale hosted SHA reproduced before the code correction; exact post-merge acceptance is owned by 0015 | PASS |
| TC-1405 | `npm test`; `npm run validate`; `git diff --check` | 125 tests passed and 7 database tests skipped locally; build/lint/typecheck and 22 architecture checks passed; patch hygiene passed. CI provides the real-PostgreSQL rerun | PASS |

## Failures and Corrections

1. Hosted health initially returned stale release SHA
   `8698bddeb86efb823d0884172164a016478c5952`. Railway `RELEASE_COMMIT_SHA` contained a literal value.
   A dashboard `${{RAILWAY_GIT_COMMIT_SHA}}` reference then resolved empty because Git variables are
   injected only for GitHub-triggered builds/deployments. The runtime now consumes Railway's native
   variable directly and gives it precedence over the legacy field.
2. Hosted default-ACL ownership differed from the simulated local owner model. Documentation now
   distinguishes the successful current-table revoke from immutable provider-owned defaults.
3. The first local npm attempts could not find `uv`, then could not write its user cache. The exact
   repository-pinned `uv 0.12.5` binary and a workspace-local ignored cache were used; all repeated
   gates passed without changing dependencies.
4. The first `npm run validate` found that the combined heading `Architecture and Structure
   Preservation` did not satisfy the exact development-record convention. Architecture decisions
   and structure-preservation evidence were separated under their required headings; the repeated
   validator passed all 22 checks.

## Final Status

**Final status:** PASS
