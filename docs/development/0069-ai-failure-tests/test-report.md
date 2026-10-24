# Test Report: 0069 AI Failure Tests

- Increment ID: `0069-ai-failure-tests`
- Date: 2026-09-20
- [Development record](./development.md)

## Environment

- Windows workspace and PowerShell
- Node.js/npm repository toolchain
- Python 3.12 API/Worker environments managed by `uv`
- Docker Desktop PostgreSQL 16 at `127.0.0.1:5432`
- Deterministic fake Provider adapters, clock, sleeper, random source and authorization policy
- No real Provider credentials, paid calls or customer data

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-6901 | Unit | Primary succeeds on initial call | One invocation and one Usage record; no sleep/Fallback |
| TC-6902 | Unit | Retryable timeout then success | One injected Full-Jitter delay; retry_no 0 then 1; two records |
| TC-6903 | Negative | Auth/safety/quota/unknown/invalid failure or exhausted rate limit | Permanent errors stop once; rate limit stops after two; no Fallback |
| TC-6904 | Adapter/Accounting | Provider returns malformed JSON with valid numeric Usage | Non-retryable invalid response; complete failed priced Usage; raw body absent |
| TC-6905 | Unit | Fallback policy missing, denies one condition or raises | Fail closed; no Fallback call |
| TC-6906 | Unit | Exhausted eligible Primary then failing/successful Fallback | Exactly one Fallback; terminal failure; total invocations never exceed three |
| TC-6907 | Contract | Inspect Migration and Ledger adapter | Attempt UUID unique/non-null; same-ID persistence duplicates neither row nor metric |
| TC-6908 | Unit | Timeout has no Provider Usage | Failed/unavailable record with NULL token/cost values, never zero |
| TC-6909 | Unit | Complete/unavailable in-memory invariants | Invalid combinations rejected before persistence |
| TC-6910 | PostgreSQL | Upgrade schema, insert duplicate and coherence violations | Unique/coherence constraints reject invalid state; valid NULL accounting persists |
| TC-6911 | Security | Sensitive request and policy exception during failure | Logs contain bounded error metadata only; no sensitive value |
| TC-6912 | Architecture/Regression | Inspect composition and run full gates | No real Primary/Fallback/customer path; all repository gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-6901–TC-6909, TC-6911 | Focused Worker failure/adapter/Ledger suites | 30 post-review unit tests passed | PASS |
| TC-6907, TC-6912 | `node --test` for 0069, Usage and Provider candidate contracts | 11 passed | PASS |
| TC-6910 | `pytest -q apps/api/tests/test_usage_records_postgres.py` with local PostgreSQL | 18 passed | PASS |
| TC-6906–TC-6910 | Final focused failure policy + real idempotent persistence test | 17 passed | PASS |
| TC-6912 | `npm test` with local PostgreSQL | 960 passed, 1 unrelated environment-gated test skipped | PASS |
| TC-6912 | `npm run lint` | Web/API/Worker lint passed | PASS |
| TC-6912 | `npm run typecheck` | Web/API/Worker strict type checks passed | PASS |
| TC-6912 | `npm run build` | Web production build and API/Worker compile builds passed | PASS |
| TC-6911–TC-6912 | `npm run scan:secrets` | 825 publishable text files inspected; no finding | PASS |
| TC-6912 | `npm run scan:dependencies` | npm/API/Worker audits found no blocking vulnerabilities | PASS |
| TC-6912 | `npm run validate` | 23 architecture/development-record gates passed after report finalization | PASS |
| TC-6912 | `git diff --check` | No whitespace errors | PASS |

## Failures and Corrections

- The first sandboxed Python run could not access the user-scoped `uv` cache. It was rerun with
  approved external access.
- Initial typecheck found Python exception-variable lifetime errors in the identity-mismatch branch;
  the local variable was separated and typecheck passed.
- Initial Fallback tests exposed an early raise at Primary retry exhaustion. The coordinator now
  distinguishes a non-retryable failure from exhausted eligible Retry and evaluates Fallback only
  in the latter case.
- Senior review found that malformed structured output can still carry valid numeric Provider
  Usage. Adapters now preserve only that safe numeric metadata, and the Ledger prices the failed
  attempt completely without storing raw output.
- Senior review also found that an idempotent duplicate INSERT could still emit a second operational
  cost metric. Metric emission now depends on a successful INSERT, and PostgreSQL integration tests
  prove one row and one metric for two persistence attempts with the same ID.
- The first architecture validation correctly rejected this report while its final status and
  remaining gate rows were `PENDING`. After all gates completed, the report was finalized and
  validation passed.

## Deferred Verification

- Real Provider calls, quality comparison, Primary/Fallback promotion and customer-content handling
  are explicitly outside this PASS.
- Hosted runtime fallback is not claimed; no runtime candidate is configured.

## Final Status

**Final status:** PASS
