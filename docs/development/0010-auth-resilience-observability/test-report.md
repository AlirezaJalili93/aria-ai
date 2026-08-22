# Test Report: 0010 Auth Resilience and Observability

- Increment ID: `0010-auth-resilience-observability`
- Date: 2026-08-18
- [Development record](./development.md)

## Environment

- Local OS: Windows; branch `agent/staging-runtime`.
- Python: 3.12.13 clean uv environment; uv 0.12.5.
- API: FastAPI 0.141.1; JWT: `PyJWT[crypto]` 2.13.0.
- Auth fixtures: generated P-256 keys plus loopback rotating/malformed JWKS servers; no hosted or
  private token was stored.
- Approved Auth contract: ES256, 30-second clock skew, 600-second JWKS cache, five-second JWKS timeout.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1001 | Contract/API | Malformed, expired, mismatched, unknown-key, bad-signature, or invalid-subject token | Safe `401 AUTH_REQUIRED`; never 503 |
| TC-1002 | Contract/API | JWKS network, DNS/timeout-equivalent, or malformed-provider response | Retryable `503 AUTH_PROVIDER_UNAVAILABLE` |
| TC-1003 | Contract | Construct Supabase JWKS client | Explicit timeout is exactly five seconds |
| TC-1004 | Security/Integration | Verify success, rejection, missing credential, and provider outage | Approved safe Auth event and trace fields; no JWT/header/claims |
| TC-1005 | Integration | Unknown `kid` triggers successful JWKS refresh | `auth.jwks_refreshed` emitted; rotated key succeeds without restart |
| TC-1006 | Static architecture | Inspect HTTP middleware | No `BaseHTTPMiddleware`; pure ASGI implementation |
| TC-1007 | Integration | Downstream enriches request trace | Completion event sees enrichment in the same ASGI context |
| TC-1008 | Unit | Enrich account/project/job trace identifiers | UUIDs canonicalized; explicit current context required |
| TC-1009 | Security/Integration | Unhandled exception occurs | Type/component/operation logged without exception message |
| TC-1010 | Contract | Emit any structured event | `schema_version` is always string `"1"` |
| TC-1011 | Security/Unit | Emit approved AI telemetry plus raw content attempts | Safe numeric/name fields retained; prompt/response discarded |
| TC-1012 | Repository gate | Run complete quality and architecture suite | Required gates pass; any unrelated pending hosted evidence remains truthful |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-1001 | Invalid-token matrix plus API mapping | All token-owned failures produced safe reason codes and 401 mapping | PASS |
| TC-1002 | Loopback connection refusal, malformed JWKS, and API outage stub | Infrastructure failures produced neutral unavailable errors and approved retryable 503 | PASS |
| TC-1003 | Constructor mock plus static contract | `PyJWKClient` received `timeout=5`, cache lifespan 600 and cache enabled | PASS |
| TC-1004 | Captured success/missing/invalid/unavailable request logs | Correct Auth events contained trace/provider/reason/timing only; secrets and subjects absent | PASS |
| TC-1005 | Two-generation loopback JWKS | Second fetch emitted refresh event and verified the rotated key without restart | PASS |
| TC-1006 | `npm run test:ci` source fitness test | `BaseHTTPMiddleware` absent and direct ASGI callable present | PASS |
| TC-1007 | Downstream job enrichment endpoint | Completion event retained the enriched job UUID | PASS |
| TC-1008 | Bound-context enrichment unit test | Account/project/job UUIDs canonicalized and context reset after scope | PASS |
| TC-1009 | Unhandled `ValueError` fixture | Type/component/operation logged; unique exception message absent | PASS |
| TC-1010 | Structured event assertions and static contract | Every observed event included string `schema_version="1"` | PASS |
| TC-1011 | AI metadata allowlist negative test | Approved numbers/names retained; raw prompt and response discarded | PASS |
| TC-1012 | Full gates listed below | All increment gates passed; global validator retained only unrelated hosted-evidence pending state | PASS |

### Final command evidence

| Command | Actual result | Status |
|---|---|---|
| Contract-first static Red run | 4 passed, 3 expected failures: timeout, pure ASGI and schema version absent | EXPECTED RED |
| Focused Auth/observability Python suite | 32 passed after final subject regression case | PASS |
| `npm run test:ci` | 22 passed | PASS |
| `npm run test:web` | 4 passed | PASS |
| `npm run test:api` | 56 passed; existing TestClient and cache-permission warnings only | PASS |
| `npm run test:worker` | 14 passed; cache-permission warning only | PASS |
| `npm run lint` | Web ESLint plus API/Worker Ruff passed | PASS |
| `npm run typecheck` | Web TypeScript plus strict API/Worker MyPy passed | PASS |
| `npm run build` | Next.js production build and API/Worker compileall passed | PASS |
| `npm audit --audit-level=high` through repository scanner | 0 vulnerabilities | PASS |
| `pip-audit==2.10.1` with OSV, API and Worker locked requirements | No known vulnerabilities in either set | PASS |
| `npm run scan:secrets` | 144 publishable text files inspected; no finding | PASS |
| `npm test` | Records 6, CI 22, Web 4, API 56 and Worker 14 tests passed | PASS |
| `npm run validate` | All architecture/content checks passed except the truthful pre-existing `0007-staging-runtime` hosted-evidence status | PASS (increment) |

## Failures and Corrections

1. The contract-first static run failed exactly three new requirements before implementation:
   missing five-second timeout, `BaseHTTPMiddleware`, and missing schema version. All pass after the
   implementation.
2. The existing writable-state API virtual environment contained a stale installed shared package;
   a clean isolated uv environment was used for final Python verification.
3. The first repository Python vulnerability scan could not access uv's global Windows tool lock.
   A second local-tool attempt exceeded twelve minutes and was terminated. The exact exported locked
   requirements were then audited directly and successfully with pip-audit 2.10.1's bounded OSV
   service; both reports contain no known vulnerability.
4. Senior review added explicit PyJWT `InvalidSubjectError` handling and a non-string subject
   regression case before the final full run.

## Final Status

**Final status:** PASS
