# Test Report: 0009 Auth Provider Integration

- Increment ID: `0009-auth-provider-integration`
- Date: 2026-08-18
- [Development record](./development.md)

## Environment

- Local OS: Windows
- Branch: `agent/staging-runtime`
- Python: 3.12 repository pin
- uv: 0.12.5
- API: FastAPI 0.141.1
- JWT: `PyJWT[crypto]` 2.13.0 with locked `cryptography` dependency
- Auth fixtures: locally generated P-256 keys and a loopback rotating JWKS server; no private or
  hosted token is stored

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-0901 | Integration/Contract | Verify a correctly signed Supabase-style ES256 token | Provider-neutral UUID identity is returned |
| TC-0902 | Security | Invalid signature, issuer, audience, expiry, subject, token shape, algorithm or `kid` | Verification fails closed with `InvalidAccessToken` |
| TC-0903 | Security/Time | Token expires within or beyond approved 30-second skew | Within-window token passes; beyond-window token fails |
| TC-0904 | API | Missing Bearer credentials | Stable `AUTH_REQUIRED` 401 envelope and Bearer challenge |
| TC-0905 | API/Security | Invalid Bearer token | Same safe 401; token absent from response and logs |
| TC-0906 | Architecture | Inspect Application/Domain imports and exact dependency pin | PyJWT exists only in Supabase Infrastructure adapter at 2.13.0 |
| TC-0907 | Integration/Rotation | Cached JWKS receives a token with a newly published `kid` | JWKS refreshes and new token verifies without restart |
| TC-0908 | Security | Token/JWK algorithm mismatch | PyJWT 2.13 binding rejects the mismatch |
| TC-0909 | Regression | Call public Health without credentials | Health succeeds and verifier is not invoked |
| TC-0910 | Scope/Contract | Inspect routes and Identity module | No product route, `/me`, account, membership or tenant behavior added |
| TC-0911 | Quality | Run lint, strict type-check, builds and repository tests | All implemented gates pass |
| TC-0912 | Security/Supply chain | Run dependency and secret scans | No blocking vulnerability or secret finding |
| TC-0913 | Architecture | Run repository validator | S1-B01 checks pass; only truthful pre-existing A03 hosted-evidence blocker may remain |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0901 | Focused Auth contract suite | Valid ES256/JWKS token returned only its UUID subject | PASS |
| TC-0902 | Invalid-token parameter matrix and signature case | Malformed, expired, wrong claim/algorithm/key/signature cases were rejected | PASS |
| TC-0903 | 28-seconds-expired and more-than-30-seconds-expired fixtures | Exact approved skew boundary behavior passed | PASS |
| TC-0904 | API dependency test without Authorization | 401 envelope, request UUID and Bearer challenge matched | PASS |
| TC-0905 | API dependency with unique invalid secret token | 401 returned; token absent from response and structured log | PASS |
| TC-0906 | `npm run test:ci`; architecture import scan | Exact pin and single Infrastructure importer enforced | PASS |
| TC-0907 | Two-generation loopback JWKS contract | New `kid` caused the second fetch and verified without restart | PASS |
| TC-0908 | JWK marked ES384 with an ES256 token | Algorithm mismatch was rejected | PASS |
| TC-0909 | Public `/health/live` regression | 200 returned with zero verifier calls | PASS |
| TC-0910 | Route/module inspection and regression suite | Only Health remains exposed; later Identity stories absent | PASS |
| TC-0911 | `npm run lint`; `npm run typecheck`; `npm run build`; repository test suites | Web 4, API 47, Worker 14 and CI/contract 17 tests passed; lint, strict types and clean build passed | PASS |
| TC-0912 | `npm run scan:dependencies`; `npm run scan:secrets` | No blocking npm/API/Worker vulnerability; 137 publishable text files had zero secret findings | PASS |
| TC-0913 | `npm run validate` | Every S1-B01 architecture/content check passed; validator remained globally non-zero only for truthful pre-existing `0007-staging-runtime` hosted evidence | PASS |

## Failures and Corrections

1. Contract-first Red execution failed collection because the Auth Adapter, API dependency and
   Application port did not yet exist. This was the expected pre-implementation failure.
2. Strict MyPy rejected the first exception-handler signature; it was corrected to Starlette's
   callback contract.
3. Senior review found that the first Runtime factory duplicated `/auth/v1` in the issuer. The
   configured canonical issuer is now used unchanged and protected by a regression assertion.
4. The first full Web build found stale Turbopack metadata pointing to a previously removed cache
   file. The generated `apps/web/.next` directory was path-validated and removed;
   a clean production build then compiled and prerendered successfully.

## Final Status

**Final status:** PASS
