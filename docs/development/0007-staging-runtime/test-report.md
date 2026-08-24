# Test Report: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Local OS: Windows
- Branch: `agent/staging-runtime`
- Node.js: 24.x repository pin
- Python: 3.12 repository pin
- uv: 0.12.5
- Hosted target: Vercel Web, Railway API/Worker, Supabase PostgreSQL/Auth/Storage, and a separately
  managed Redis-compatible free Queue
- Supabase staging: `hqgfqlvfwflbazsuhazs`, Frankfurt `eu-central-1`, `ACTIVE_HEALTHY`
- Railway Trial: active; 25 days or USD 5 credit remained at the latest readback
- Railway runtime target: EU West Metal Amsterdam (`europe-west4-drams3a`)
- Queue target: Frankfurt (`eu-central-1`), TLS, persistent, no eviction
- Secret values: never recorded in this report

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-0701 | Build/Runtime | Build all three deployables and validate hosted fail-fast settings | Web, API, and Worker build; Staging rejects missing critical configuration |
| TC-0702 | API/Contract | Call `/health/live` while dependency probes are unavailable | Stable non-sensitive 200 response; no dependency probe is called |
| TC-0703 | API/Runtime | Call `/health/ready` with available/unavailable database and Queue probes | Both ready returns 200; either unavailable returns sanitized 503; no AI check occurs |
| TC-0704 | Security/Config | Inspect frontend allowlist, deployment artifacts, and secret scanner | No backend/provider secret is bundled or committed |
| TC-0705 | Hosted smoke | Open latest staging Web URL and call hosted API liveness/readiness | Web and API are reachable over TLS and report staging/version/release metadata |
| TC-0706 | Isolation | Read back Supabase, Queue, Railway services, regions, and bindings | Staging resources are independent, private where required, and reference no Production identifier |
| TC-0707 | Deployment | Validate source branch, exact SHA, release config, rollback, and cost state | Deployment is PR-gated, uses approved temporary Trial credit, and identifies the exact commit |
| TC-0708 | Quality/Architecture | Run repository tests, builds, scans, validation, and Senior review | All gates pass with no unresolved implementation finding |
| TC-0709 | Contract | Validate Railway API/Worker Config-as-Code and locked Dockerfiles | Separate non-root deployables, one EU region, readiness admission, bounded restart, no branch/secret values, and no Render residue |
| TC-0710 | Regression | Normalize a Supabase/libpq `sslmode=require` URI for SQLAlchemy asyncpg without changing unrelated query parameters | asyncpg receives `ssl=require`; focused readiness tests pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0701 | GitHub Quality build; Railway API `6508b8f2`; Worker deployment readback | Web/API/Worker builds passed; API and Worker are Active and API readiness admission passed | PASS |
| TC-0702 | `npm run test:api` | Liveness returned exact 200 metadata and made zero dependency calls | PASS |
| TC-0703 | `npm run test:api` | DB/Queue readiness returned 200/503 as specified; real loopback RESP `PING` passed; responses were sanitized | PASS |
| TC-0704 | `npm run test:ci`; `npm run scan:secrets` | 27 CI/contract tests passed; 166 publishable text files scanned with zero secret findings | PASS |
| TC-0705 | Exact-SHA Vercel readback and HTTP request; hosted Railway health requests | Vercel Preview is READY at `f3752ca...` and returned 200; API `/health/live` and `/health/ready` both returned 200 with exact release SHA and sanitized metadata | PASS |
| TC-0706 | Post-rotation Supabase SQL readback; Railway inspection; direct Queue TLS probe | Supabase `SELECT 1` returned one; private bucket and official Session Pooler host/port/user were verified; authenticated Queue `PING/PONG` passed | PASS |
| TC-0707 | Config test; hosted source/deployment readback; prior-artifact rollback/redeploy selection | API and Worker are Active at `f3752ca...`; Trial remained within approved credit; Railway exposed rollback/redeploy for the prior same-SHA artifact and deduplicated the no-op selection without service degradation | PASS |
| TC-0708 | GitHub Quality/Security; local focused tests; `npm run validate` | At `f3752ca...`, lint, strict types, builds, Records 6, CI/contract 23, Web 4, API 57, and Worker 14 passed; Security baseline passed; final local validation passed all 22 checks | PASS |
| TC-0709 | `node --test scripts/test/deployment-config.test.js` | 7/7 Railway migration/runtime-root contract tests passed; Render Blueprint is absent | PASS |
| TC-0710 | `.tools/venv-api/Scripts/python.exe -m pytest -q apps/api/tests/test_database_readiness.py apps/api/tests/test_health.py` | 8/8 passed; `sslmode=require` is adapted to `ssl=require` and unrelated query parameters are preserved | PASS |

## Failures and Corrections

1. The original provider required a payment card before repository or resource creation. No resource
   was created and no charge occurred. ADR-007 replaces that proposal with temporary Railway Trial
   services and a separately managed free Queue.
2. Koyeb Free was rejected because it allows only one free Web Service and explicitly cannot run a
   Worker Service. Northflank was rejected because all plans require a payment method. Demo runtimes
   that sleep were rejected for Worker semantics.
3. Railway offers no Frankfurt runtime. Its only EU Metal runtime is Amsterdam; this proximity
   compromise is documented as Staging-only and is not promoted to Production architecture.
4. The first focused contract run had 5/6 passing because the test expected a shell-form Worker
   command while the safer Dockerfile used JSON exec form. The matcher was corrected without
   weakening the required `uv run --project apps/worker --no-sync` assertion; 6/6 then passed.
5. Local Docker image execution could not run because no Docker daemon was active. No local image
   result is claimed; the Railway hosted build remains the required evidence.
6. Railway OAuth succeeded and activated the 30-day/USD 5 Trial. Resource creation initially paused
   at the provider's Terms of Service; the owner personally accepted them before provisioning.
7. The first post-migration secret scan failed because `git ls-files` also lists tracked files deleted
   in a dirty worktree. The scanner now skips missing tracked paths, a temporary-repository regression
   test proves that behavior, and the full scan passes without weakening any detector.
8. Hosted Worker deployment `72b74b0d` built but crashed at startup with
   `ModuleNotFoundError: No module named 'app'`. Contract-first regression evidence failed 1/7 before
   the fix and passed 7/7 after setting the Worker image import root explicitly. Hosted redeployment
   was then required and subsequently completed before TC-0701 passed.
9. Redeployment `6da02478` proved the Worker import correction, then fail-fast rejected missing
   `database_url`, `queue_broker_url`, `release_commit_sha`, and Storage credentials. API deployment
   `dcd03984` likewise built and rejected the same missing dependencies plus `public_app_url`.
   `API_BASE_URL` exists but is intentionally not substituted for the documented `PUBLIC_APP_URL`.
10. Railway deployment `35f2d219` rejected a multiline Upstash REST sample in
    `QUEUE_BROKER_URL`. The value was replaced with the required single TLS Redis-compatible DSN on
    API and Worker; no credential was written to disk or emitted to logs. Direct authenticated
    `PING/PONG` then passed.
11. API deployment `b54d1caf` started Uvicorn but returned sanitized 503 readiness responses. A
    local Driver reproduction showed SQLAlchemy forwarded the Supabase URI's `sslmode` query key as
    an unsupported asyncpg keyword. Contract-first regression coverage passed 8/8 after commit
    `3005e0d` adapted that key to `ssl`.
12. API deployment `73e1494c` built and started from `3005e0d` without a configuration validation
    error, but its PostgreSQL readiness probe still failed for the full five-minute admission
    window. Supabase `SELECT 1`, the official Session Pooler host/port/user, and Queue authentication
    independently passed. The dashboard-only database password was the remaining unverified input;
    it was not guessed, displayed, or changed before the owner authorization recorded in item 14.
13. The first TC-0710 fixture contained a credential-shaped placeholder URL and the Secret Scanner
    rejected it. Commit `f3752ca` constructs the same inert fixture from fragments; focused tests
    remain 8/8 and the full Secret Scanner passes 166/166 files without an exception or allowlist.
14. After explicit owner authorization, the isolated Staging database password was rotated and the
    new Session Pooler DSN was transferred in memory to Railway API and Worker. No secret was printed,
    written to repository files, or included in this report. Post-rotation `SELECT 1` passed.
15. Railway deployment `6508b8f2` passed internal `/health/ready` with 200, but public requests first
    failed because the domain targeted port `8000` while Uvicorn listened on `8080`. Updating the
    public target to `8080` restored `/health/live` and `/health/ready`, both with HTTP 200.
16. The rollback drill invoked the previous artifact's `Rollback`/`Redeploy` controls. Both previous
    and active artifacts referenced the same SHA and current environment, so Railway deduplicated the
    no-op selection; the active deployment and public health remained successful.
17. A final `npm test` attempt on the shared dirty worktree passed Records 6, CI/contract 27, and Web
    4 before API collection encountered the stale local editable `aria_observability` installation
    required by the uncommitted S1-B02 work. This is not release evidence for Increment 0007 and no
    S1-B02 environment or source was changed to mask it; the clean exact-SHA GitHub run above remains
    the Increment 0007 suite evidence.

## Final Status

**Final status:** PASS
