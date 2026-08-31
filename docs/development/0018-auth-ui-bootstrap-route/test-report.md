# Test Report: 0018 Auth UI and Bootstrap Route

- Increment ID: `0018-auth-ui-bootstrap-route`
- Date: 2026-08-25
- [Development record](./development.md)

## Environment

- Windows local workspace, branch `codex/s1-b05-auth-ui`.
- Node.js `v24.11.1`; npm `11.6.2`; Python `3.12.14`; Next.js `16.3.1`.
- Supabase Staging `aria-ai-staging`, Frankfurt `eu-central-1`, status `ACTIVE_HEALTHY`.
- GitHub-hosted Ubuntu 24.04 Quality runner with PostgreSQL `16-alpine` service for the mandatory
  database run.
- Hosted verification SHA: `e8a048e4c727b769c8d9d83f799bb711fa310232`.
- Vercel Preview deployment `D5pcva4roeTm2b4mGAHJcsrdQCwd`, status Ready, branch
  `codex/s1-b05-auth-ui`.
- Railway Staging API deployment `5f6e2aa1-7b54-4582-8fb8-52f1f6ceca54` and private Worker
  deployment `03fa122f-1b35-4abc-aa3f-cab962adb756`, both successful for the hosted verification
  SHA.
- Local Next.js development runtime connected with the active non-secret Supabase publishable key;
  no real user identity, mailbox, password, or JWT was used.
- Browser widths: 375, 768, 1024 and 1440 CSS px at 900px height.
- Hosted verification date: 2026-08-31.
- Post-merge verification branch: `codex/s1-b05-final-seal`; merge SHA
  `fdcd9d3f617a1afa328d5ccb1cd30f34b5926ac9`.
- Post-merge Railway deployments: API `e43f7b64-208f-48e6-adaf-2bc2691b7506`; Worker
  `3cf3165e-714b-45bd-997d-105816fb234a`.
- Corrected Vercel main deployment: `9RRDRSGatdcxmhJ4mQqy1uAKZuhj`, current Production channel for
  the exact merge SHA. The Vercel channel consumes the approved Staging public dependencies; it is
  not a product-Production acceptance environment.

## Test Cases

| ID | Layer | Expected result | Final result |
|---|---|---|---|
| TC-1801 | Web interaction | Login uses Email/Password, exposes pending/error state and redirects only after Bootstrap | PASS |
| TC-1802 | Web interaction/scope | Signup uses Email/Password, shows «ایمیل تأیید ارسال شد», and contains no Magic Link/Recovery/Consent | PASS |
| TC-1803 | Web callback | valid code or approved email token resolves a session, calls Bootstrap, then redirects `/projects` | PASS — contract/build; live mailbox is a deployment check |
| TC-1804 | Web protected route | unauthenticated `/projects` redirects to Login; authenticated route renders first-use state and CTA | PASS |
| TC-1805 | Negative journey | pre-verification Signup cannot redirect to `/projects` | PASS |
| TC-1806 | Negative callback | missing/invalid/expired callback shows safe recoverable error with no query secret retained | PASS |
| TC-1807 | API contract | authenticated `POST /api/v1/auth/bootstrap` needs no tenant header/body and returns empty 204 | PASS |
| TC-1808 | API idempotency | repeated already-Bootstrapped request returns 204, never 409 or data | PASS |
| TC-1809 | API Auth | missing/malformed/expired JWT maps to 401 `AUTH_REQUIRED` | PASS |
| TC-1810 | API provider failure | JWKS/provider failure maps to retryable 503 `AUTH_PROVIDER_UNAVAILABLE` | PASS |
| TC-1811 | API bootstrap failure | internal Bootstrap failure maps to stable retryable infrastructure error | PASS |
| TC-1812 | Database regression | existing concurrency/idempotency PostgreSQL cases still pass | PASS — PostgreSQL 16 CI |
| TC-1813 | Logging | exact approved Auth and Bootstrap event names carry request/correlation metadata | PASS |
| TC-1814 | Logging privacy | Email, password, JWT, callback token/query and raw subject never enter logs | PASS |
| TC-1815 | Legal scope | no Terms/Privacy URL, consent version or persistence is invented | PASS |
| TC-1816 | Accessibility | labels, semantic controls, status/error announcements, focus visibility and keyboard flow pass | PASS |
| TC-1817 | RTL/LTR | Persian shell is RTL; Email and identifiers remain LTR | PASS |
| TC-1818 | Responsive | 375, 768, 1024 and 1440px layouts have no overflow or clipped controls | PASS |
| TC-1819 | Design tokens/motion | no raw component colors; 44px controls and reduced-motion handling remain enforced | PASS |
| TC-1820 | Repository gates | `npm test` and `npm run validate` pass with complete records | PASS |
| TC-1821 | Hosted exact-SHA deployment | Vercel Web and Railway API/Worker deployment contexts identify the full PR SHA; API live/ready and internal checks pass | PASS |
| TC-1822 | Hosted Auth smoke/privacy | Login rejection, invalid Callback, protected route, Auth API errors and deployment logs preserve the approved contracts without sensitive data | PASS |
| TC-1823 | Post-merge exact-SHA promotion | Main CI, Railway API/Worker and Vercel Web identify the merge SHA; hosted API readiness passes | PASS |
| TC-1824 | Post-merge runtime regression | A build-ready/runtime-broken Vercel deployment is detected, corrected through environment scoping, redeployed, and fully re-smoked | PASS |

## Execution Results

| Cases | Command/evidence | Actual result | Status |
|---|---|---|---|
| TC-1807–TC-1814 | `npm run test:api` | 89 passed; 10 PostgreSQL-only cases skipped because no local server; one upstream Starlette/httpx deprecation warning | PASS |
| TC-1807–TC-1815 | `npm run test:ci` | 41/41 architecture, contract, deployment and security tests passed | PASS |
| TC-1801–TC-1806, TC-1813–TC-1819 | `npm run test:web` | 11/11 Auth/UI source-contract tests passed | PASS |
| Regression | `npm run test:worker` | 16/16 passed | PASS |
| Static quality | `npm run lint:web`; `npm run lint:api`; `npm run typecheck:web`; `npm run typecheck:api` | ESLint, Ruff, TypeScript Strict and MyPy passed | PASS |
| TC-1801–TC-1806, TC-1816–TC-1819 | `npm run build:web` | Optimized build compiled; all Auth/Projects routes and Proxy emitted | PASS |
| TC-1814, TC-1820 | `npm run scan:secrets` | 218 publishable text files inspected; no secret detected | PASS |
| TC-1820 | `npm run scan:dependencies` | npm/API/Worker scans found no blocking vulnerability | PASS |
| TC-1801, TC-1814 | Browser + real Supabase public config, invalid synthetic Login | Provider returned rejection; Persian safe message shown; URL unchanged; event contained only IDs, reason and duration | PASS |
| TC-1806, TC-1814 | Browser + invalid synthetic callback token | Redirected to scrubbed `/auth/callback/error?reason=invalid_or_expired`; no credential appeared in framework/event log | PASS |
| TC-1816–TC-1819 | Browser computed-layout checks | RTL root, LTR Email, 44px controls, no horizontal overflow at 375/768/1024/1440, no error dialog | PASS |
| TC-1802, TC-1805 | Supabase `/auth/v1/settings` read-only check | Email enabled; Signup enabled; all social providers disabled; `mailer_autoconfirm=false` | PASS |
| TC-1809, TC-1810 | Supabase public JWKS read-only check | Active signing key reports `kty=EC`, `alg=ES256`, `use=sig` | PASS |
| TC-1820 | `git diff --check` | No whitespace error | PASS |
| TC-1820 | `npm run quality` | Full lint, strict typecheck, 6 record tests, 41 contract tests, 11 Web tests, 89 API tests, 16 Worker tests, all builds, and 22 architecture checks passed | PASS |
| TC-1820 | Final documentation rerun: `npm test`; `npm run validate` on 2026-08-31 | 6 record tests, 41 contract tests, 11 Web tests, 89 API tests with 10 documented local PostgreSQL skips, 16 Worker tests, and 22 architecture checks passed | PASS |
| TC-1812, TC-1820 | [GitHub Actions run 32822141009](https://github.com/AlirezaJalili93/aria-ai/actions/runs/32822141009) | Quality passed with PostgreSQL 16: 99 API tests, 16 Worker tests, 11 Web tests, 41 contract tests, all builds and 22 architecture checks; Security baseline passed | PASS |
| TC-1821 | GitHub commit/deployment status APIs; Railway hosted GET `/health/live` and `/health/ready`; Vercel deployment dashboard | Vercel Ready on exact branch/SHA; Railway API deployment `5f6e2aa1-7b54-4582-8fb8-52f1f6ceca54` and Worker deployment `03fa122f-1b35-4abc-aa3f-cab962adb756` success; live/ready HTTP 200 with full SHA match and configuration/database/queue=`pass` | PASS |
| TC-1809, TC-1822 | Hosted `POST /api/v1/auth/bootstrap` without Authorization and with a synthetic malformed Bearer | Both returned 401 `AUTH_REQUIRED`, `retryable=false`, with request IDs and no tenant-header requirement | PASS |
| TC-1801, TC-1806, TC-1816–TC-1818, TC-1822 | Exact-SHA Vercel Preview browser smoke | Login rendered with RTL root, no overflow and 44px control; synthetic invalid Login showed the safe Persian error; invalid Callback redirected to `/auth/callback/error?reason=invalid_or_expired`; unauthenticated `/projects` redirected to Login; browser console had no Warning/Error | PASS |
| TC-1814, TC-1822 | Deployment-scoped Vercel Runtime Logs | `auth.login_failed` and `auth.callback_failed` contained only safe IDs, reason and duration; synthetic Email/password/token were absent; Warning/Error/Fatal counts were zero | PASS |
| TC-1823 | [Main CI run 33363686425](https://github.com/AlirezaJalili93/aria-ai/actions/runs/33363686425); GitHub commit statuses | Quality and Security passed; Vercel, Railway API and Railway Worker statuses all succeeded for merge SHA `fdcd9d3f617a1afa328d5ccb1cd30f34b5926ac9` | PASS |
| TC-1823 | Railway post-merge hosted smoke | API deployment `e43f7b64-208f-48e6-adaf-2bc2691b7506` and Worker deployment `3cf3165e-714b-45bd-997d-105816fb234a` succeeded; live/ready returned HTTP 200 and the full merge SHA; configuration/database/queue=`pass`; missing and malformed Bootstrap credentials each returned 401 `AUTH_REQUIRED`, `retryable=false` | PASS |
| TC-1824 | Initial Vercel main deployment `Hoa4xrTr2t3qWu8vf1bGt985FfrJ`; direct HTTP and deployment logs | Build status was Ready, but `/`, `/auth/login`, `/projects` and Callback requests returned 500; deployment log reported `AuthConfigurationError` because the four required Auth runtime keys were Preview-branch scoped only | FAIL — detected and corrected |
| TC-1824 | Vercel environment-scope readback and redeploy `9RRDRSGatdcxmhJ4mQqy1uAKZuhj` | Separate Config entries for `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL`, `PUBLIC_APP_URL` and `NEXT_PUBLIC_SUPABASE_URL` exist in Production scope; redeploy is Ready/current for exact merge SHA; no value was committed or copied into test evidence | PASS |
| TC-1801, TC-1806, TC-1809, TC-1814, TC-1824 | Corrected Vercel Production HTTP/browser/log smoke | Login HTTP 200 and safe Persian invalid-credential message; invalid Callback HTTP 303 to `/auth/callback/error?reason=invalid_or_expired`; unauthenticated `/projects` resolved to `/auth/login`; approved safe events present; synthetic Email/password, `AuthConfigurationError` and post-correction GET 500 absent | PASS |
| TC-1820, TC-1823, TC-1824 | Post-merge final-seal rerun: `npm test`; `npm run validate`; `npm run scan:secrets`; `git diff --check` | 6 record, 41 contract, 11 Web, 89 API with 10 documented local PostgreSQL skips, and 16 Worker tests passed; 22 architecture checks passed; 218 files passed secret scan; no whitespace error | PASS |

## Failure and Correction History

- First production build failed because a `"use server"` module exported initial Action state.
  Shared state moved to `features/auth/types.ts`; the subsequent build passed.
- First Ruff run found one import-order issue in `apps/api/app/main.py`; order corrected and Ruff
  rerun passed.
- Senior review found the route was using active-Membership authorization. It was changed to the
  authenticated identity-only pre-tenant dependency, 403 was removed from the route/OpenAPI, and a
  suspended-Membership regression test was added; API count increased to 89 passed.
- Browser review found Next.js development request logging exposed callback query strings. The
  callback path is now excluded from incoming request logs, credentials are scrubbed before every
  redirect, and the exact browser scenario was rerun without token disclosure.
- The first final-documentation `npm test` attempt was stopped before API execution because the
  restricted workspace could not open the existing external `uv` cache. The identical command was
  rerun with approved cache access; all executable local tests passed with only the documented ten
  PostgreSQL-dependent skips. No source or test configuration was changed to obtain the pass.
- The first post-merge Vercel deployment was build-ready but runtime-broken. Direct HTTP returned
  500 and deployment logs reported `AuthConfigurationError`; environment readback proved all four
  required keys were limited to the PR Preview branch. Separate Production-scoped Config entries
  were created without committing or logging their values. Redeploy `9RRDRSGatdcxmhJ4mQqy1uAKZuhj`
  at the same merge SHA passed the repeated HTTP, browser, redirect and log checks.

## Final Status

**Final status:** PASS
