# Test Report: 0068 Provider Adapter Candidates

- Increment ID: `0068-provider-adapter-candidates`
- Date: 2026-09-20
- [Development record](./development.md)

## Environment

- Windows workspace and PowerShell
- Node.js/npm repository toolchain
- Python 3.12 Worker environment managed by `uv`
- Docker Desktop PostgreSQL 16 at `127.0.0.1:5432`
- Deterministic fake Provider clients only; no API keys, paid calls or customer data

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-6801 | Contract | Inspect SDK pins, candidates, timeouts, retry/tool/cache restrictions and ADR | Exact approved contract; Primary/Fallback none |
| TC-6802 | Unit | Execute candidate with available/missing Price | Price resolves and is retained first; missing Price invokes no adapter |
| TC-6803 | Unit | Translate OpenAI request and successful usage | Strict JSON Schema, no tools/store, explicit cache mode, normalized counts |
| TC-6804 | Negative | OpenAI cache-write count is missing or non-zero | Fail closed; no authoritative result/ledger data |
| TC-6805 | Unit | Translate Gemini request and usage with thinking tokens | No tools/cache; output is candidates plus thoughts |
| TC-6806 | Static/Factory | Inspect client construction | Connect=5s, request/read=60s, SDK retries disabled |
| TC-6807 | Negative | Safety block, malformed output or invalid token accounting | Bounded non-retryable Provider error; no raw data exposure |
| TC-6808 | Security | Scan repository and integration boundary | No secret, customer fixture or runtime promotion |
| TC-6809 | Regression | Full tests, static checks, build and architecture validation | All repository quality gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-6801, TC-6806, TC-6808 | `node --test scripts/test/provider-candidates-contract.test.js` | 5 passed | PASS |
| TC-6802–TC-6807 | Focused Worker Provider tests | 10 passed | PASS |
| TC-6809 | `npm test` with local PostgreSQL | 932 passed, 1 unrelated environment-gated test skipped | PASS |
| TC-6809 | `npm run lint` | Web/API/Worker lint passed | PASS |
| TC-6809 | `npm run typecheck` | Web/API/Worker type checks passed | PASS |
| TC-6809 | `npm run build` | Web production build and API/Worker compile builds passed | PASS |
| TC-6808–TC-6809 | `npm run scan:secrets` | 815 publishable text files inspected; no finding | PASS |
| TC-6808–TC-6809 | `npm run scan:dependencies` outside sandbox | npm/API/Worker audits found no blocking vulnerabilities | PASS |
| TC-6809 | `npm run validate` | Architecture and development-record gates passed | PASS |
| TC-6809 | `git diff --check` | No whitespace errors | PASS |

## Failures and Corrections

- Contract-first tests initially failed because the approved SDK pins, concrete Infrastructure
  adapters, preflight executor and ADR did not exist; the implementation made them pass.
- The first Python focused run used `pytest.mark.asyncio`, but this repository intentionally has no
  pytest-asyncio dependency. Tests were corrected to use the established `asyncio.run` pattern.
- The first full regression found a stale ADR-022 contract test that still required G02/G03 to be
  Deferred. The test and ADR were updated to recognize ADR-055's explicit candidate selection while
  preserving deferred runtime promotion/fallback.
- Dependency audit could not access the user-scoped `uv` tool lock inside the sandbox. It was rerun
  with approved external access and all audits passed.
- The first architecture validation still required superseded generic Provider secret names and
  scanned the workspace-local `uv` cache. Validation now requires the approved empty OpenAI/Gemini
  keys and excludes the generated `.uv-cache`, consistent with the existing cache exclusions.
- Pytest reported non-blocking Windows cache-permission warnings and one pre-existing Starlette
  `httpx` deprecation warning; tests and production builds were unaffected.

## Deferred Verification

- Real model-quality evaluation is deliberately not part of this PASS. It requires controlled
  secrets, explicit Catalog rows and the approved synthetic fixture suites.
- Customer-data execution remains prohibited and was not tested.

## Final Status

**Final status:** PASS
