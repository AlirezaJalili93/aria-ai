# Test Report: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-18
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
- Railway Trial: 30 days or USD 5 credit; Terms acceptance pending
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

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0701 | `npm run build`; hosted-settings tests | Web/API/Worker local builds and fail-fast tests passed; Railway image build pending | PARTIAL |
| TC-0702 | `npm run test:api` | Liveness returned exact 200 metadata and made zero dependency calls | PASS |
| TC-0703 | `npm run test:api` | DB/Queue readiness returned 200/503 as specified; real loopback RESP `PING` passed; responses were sanitized | PASS |
| TC-0704 | `npm run test:ci`; `npm run scan:secrets` | 19 CI/contract tests passed; 142 publishable text files scanned with zero secret findings | PASS |
| TC-0705 | Hosted Web/API smoke | Historical Vercel Preview matched `b590f6c...`; latest Vercel SHA and Railway TLS API smoke pending | PARTIAL |
| TC-0706 | Supabase readback; Railway/Queue inspection | Supabase is healthy in Frankfurt and bucket is private; Railway and Queue readback pending | PARTIAL |
| TC-0707 | Config test; hosted deployment readback | Repository contract passes; hosted source SHA, Trial usage, logs, and rollback remain pending | PARTIAL |
| TC-0708 | `npm test`; lint; type-check; build; dependency/secret scans; `npm run validate` | 90 tests, lint, strict types, all builds, and both scans passed; validation has only the truthful hosted-evidence PENDING status | PARTIAL |
| TC-0709 | `node --test scripts/test/deployment-config.test.js` | 6/6 Railway migration contract tests passed; Render Blueprint is absent | PASS |

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
6. Railway OAuth succeeded and activated the 30-day/USD 5 Trial. Resource creation is paused at the
   provider's Terms of Service, which the owner must personally accept.
7. The first post-migration secret scan failed because `git ls-files` also lists tracked files deleted
   in a dirty worktree. The scanner now skips missing tracked paths, a temporary-repository regression
   test proves that behavior, and the full scan passes without weakening any detector.

## Final Status

**Final status:** PENDING
