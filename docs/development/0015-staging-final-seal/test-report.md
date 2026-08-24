# Test Report: Staging Final Seal

- Increment ID: `0015-staging-final-seal`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Repository: public `AlirezaJalili93/aria-ai`.
- Sealed runtime merge SHA: `f8f94d30af5a8814e20cde29ff2526bebf350a43`.
- Supabase Staging: `hqgfqlvfwflbazsuhazs`, Frankfurt, PostgreSQL 17.
- Railway Staging: API deployment `8167622b-3b26-4bfe-bf1d-edc27e023240`; private Worker
  deployment `f0dd5bb7-9ff0-4654-973b-051f334a2d92`.
- Hosted API: `https://aria-staging-api-staging.up.railway.app`.
- Verification date: 2026-08-24.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1501 | Main pipeline | Inspect PR #7 merge, main CI, migration run, and commit deployment contexts | Exact SHA has successful CI, migration, Vercel, Railway API, and Railway Worker results |
| TC-1502 | Hosted smoke | Call `/health/live` and `/health/ready` and compare full SHA | Both return HTTP 200; SHA equals deployed commit; ready checks config/DB/Queue only and all pass |
| TC-1503 | Hosted database/security | Read exact Alembic head, RLS, grants, policies, provider defaults, and advisors | Exact head; four RLS tables; zero current Data API grants; no advisor ERROR; known INFO findings routed |
| TC-1504 | Repository/governance | Confirm docs-only diff; run `npm test`, `npm run validate`, secret scan, and patch hygiene | Mandatory gates pass; no runtime/migration file changes or credential exposure |

## Execution Results

| ID | Command or evidence | Actual result | Status |
|---|---|---|---|
| TC-1501 | PR #7; main CI `32725919269`; migration run `32725919119`; GitHub commit status API | Merge SHA `f8f94d30af5a8814e20cde29ff2526bebf350a43`; CI Quality/Security PASS; idempotent migration PASS; Vercel, Railway API, and Railway Worker deployment contexts all success | PASS |
| TC-1502 | Hosted GET `/health/live`; GET `/health/ready`; strict SHA comparison | live=`alive`, HTTP 200, SHA match=true; ready=`ready`, HTTP 200, SHA match=true; configuration/database/queue=`pass` | PASS |
| TC-1503 | Supabase SQL catalog aggregate plus Security/Performance advisors | Head=`0001_identity_access_hardening`; four tables RLS=true; current grant count=0; policy count=0; provider-owned table default ACL count=16; no ERROR; four no-policy INFO and two unused-index INFO | PASS |
| TC-1504 | `git diff --name-only`; `npm test`; `npm run validate`; `npm run scan:secrets`; `git diff --check` | Documentation-only diff; 125 tests passed and 7 local DB-dependent tests skipped; 22 validation checks and secret/patch gates passed | PASS |

## Advisor Routing

- Security INFO `rls_enabled_no_policy`: intentionally remains until documented M010 policy
  selection. [Supabase remediation reference](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
- Performance INFO `unused_index`: retained pending representative Staging usage; removal is not
  authorized by current documents. [Supabase remediation reference](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).

## Failures and Corrections

- No failure occurred in the post-merge main CI, controlled migration, Vercel deployment, Railway
  API deployment, Railway Worker deployment, exact-SHA smoke, or final Supabase readback.
- Earlier stale-SHA and provider-default documentation corrections are retained in increment 0014
  and were proven by this final seal.
- The first local final-seal `npm test` attempt hit a Windows file-lock error while `uv` tried to
  resync an already-installed local package. It was repeated with the official `UV_NO_SYNC=1`
  option against the unchanged locked environment; all 125 tests passed and seven database tests
  remained locally skipped for the documented CI real-PostgreSQL rerun.

## Final Status

**Final status:** PASS
