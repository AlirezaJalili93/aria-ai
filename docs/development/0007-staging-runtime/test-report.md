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
- Hosted target: Vercel Web, Render API/Worker/Key Value, Supabase PostgreSQL/Auth/Storage
- Supabase staging: `hqgfqlvfwflbazsuhazs`, Frankfurt `eu-central-1`, `ACTIVE_HEALTHY`
- Secret values: never recorded in this report

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-0701 | Build/Runtime | Build all three deployables and validate staging fail-fast settings | Web, API, and Worker build; staging rejects missing critical configuration |
| TC-0702 | API/Contract | Call `/health/live` while the database probe is unavailable | Stable non-sensitive 200 response; database probe is not called |
| TC-0703 | API/Runtime | Call `/health/ready` with available/unavailable database and queue probes | Both bindings ready returns 200; either unavailable returns sanitized 503; no AI check occurs |
| TC-0704 | Security/Config | Inspect frontend allowlist, committed files, Blueprint placeholders, and secret scanner | No backend/provider secret is bundled or committed |
| TC-0705 | Hosted smoke | Open staging Web URL and call hosted API liveness/readiness | Web and API are reachable over TLS and report staging/version metadata |
| TC-0706 | Isolation | Read back Supabase project/bucket and Render queue bindings | Staging resources are independent, private where required, and reference no production identifier |
| TC-0707 | Deployment | Validate Render/Vercel configuration and rollback metadata | Deployment is CI-gated, same-region, within the confirmed ceiling, and identifies the commit |
| TC-0708 | Quality/Architecture | Run repository tests, builds, validation, and senior review | All gates pass with no unresolved implementation finding |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0701 | `npm run build`; hosted-settings tests | Web/API/Worker builds passed; configuration fail-fast tests passed | PASS |
| TC-0702 | `npm run test:api` | Liveness returned exact 200 metadata and made zero dependency calls | PASS |
| TC-0703 | `npm run test:api` | DB/queue readiness returned 200/503 as specified; real loopback RESP `PING` passed; response was sanitized; 24 API tests passed | PASS |
| TC-0704 | `npm run test:ci`; `npm run scan:secrets` | Typed/secret-safe config and 12 CI/deployment tests passed; 109 publishable files scanned with zero findings | PASS |
| TC-0705 | Hosted Web/API smoke | Vercel project baseline is Ready on `main` commit `a9cf7cb9b21afee35e30ad400a484b9bd1bc994b`, but it is not the approved PR SHA and therefore is not counted as Preview evidence; Render deployment remains blocked | PENDING |
| TC-0706 | Supabase project and SQL readback; hosted Render inspection | Supabase is healthy in `eu-central-1`; bucket exists with `public=false`; Render readback pending | PARTIAL |
| TC-0707 | `node --test scripts/test/deployment-config.test.js`; hosted deployment readback | Five Blueprint contract tests pass, including rejection of explicit service branch overrides; hosted price, URLs, CI gate, and release SHA remain pending | PARTIAL |
| TC-0708 | `npm run lint`; `npm run typecheck`; `npm run build`; final `npm test`; `npm run validate` | Lint/type-check/build passed; validation has only the intentionally pending hosted-evidence status | PARTIAL |

## Failures and Corrections

1. Contract-first health tests initially failed before the routes existed, confirming the tests exercised new behavior. The implementation then made all cases pass.
2. A FastAPI 0.141 lazy-router change made direct `app.routes` introspection unreliable. The bootstrap test was corrected to assert behavior through HTTP without weakening coverage.
3. The initial database readiness adapter could wait indefinitely. A bounded three-second async timeout and translated unavailable result were added.
4. The secret scanner detected a credential-shaped database URL in a unit-test fixture. The fixture now assembles representative values at runtime; the scanner remains strict and passes.
5. The first Vercel deployment request was rejected before execution because its file payload was ambiguous. No project or deployment was created; a precisely scoped deployment requires explicit source/destination confirmation.
6. Mandatory review found presence-only config, plaintext secret representation, incomplete release metadata, missing Queue readiness, and inaccurate Worker readiness semantics. Contract-first tests reproduced all gaps; typed/secret-safe settings, DB+Queue readiness, OpenAPI metadata, and truthful Worker startup semantics now pass.
7. The original Blueprint pinned API and Worker to `main`, which could make a PR preview deploy the wrong commit. A contract test now rejects any explicit service branch override, and both pins were removed before hosted verification.
8. The first precisely intended Vercel Preview call was rejected because the connector action accepts no source-project, commit, or root-scope arguments. No deployment was created; the next attempt must originate from the GitHub branch after its new HEAD is published and must prove the deployed SHA.
9. Vercel's repository import correctly created a Ready baseline from `main`, but the already-open PR branch did not appear as active because its last push preceded project connection. The baseline is explicitly excluded from hosted smoke evidence; this documentation update is the branch event used to request a new Preview.

## Final Status

**Final status:** PENDING
