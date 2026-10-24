# Test Report: 0033 Parser Metrics

[Development record](./development.md)

## Environment

- Windows 11 host, repository worktree `staging-migrations`
- Python 3.12 Worker environment managed by `uv`
- Node.js/npm repository toolchain
- Metrics tests use an in-memory spy; no external metrics backend is used

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3301 | Contract | Inspect ParserMetrics port and bounded labels | Latency, queue-wait and outcome operations exist; only approved dimensions are represented |
| TC-3302 | Unit | Successful Text Parser invocation | Parser latency is recorded from parser entry through success and outcome is success |
| TC-3303 | Unit | Empty normalized text | Empty failure records latency and bounded `empty` failure class |
| TC-3304 | Contract/unit | Validate outcome dimensions | Success cannot carry failure class; failure requires a bounded class; identifiers are absent from metric calls |
| TC-3305 | Observability | Inspect parser lifecycle logging | Started/succeeded/failed events are safe and content-free; trace context remains the identifier channel |
| TC-3306 | Regression | Run Worker tests | Existing Worker runtime, queue and parser behavior remains green |
| TC-3307 | Quality | Run repository quality gates | Lint, typecheck, tests, build and architecture validation pass |

## Execution Results

| ID | Command | Actual | Status |
|---|---|---|---|
| TC-3301, TC-3304, TC-3305 | `node --test scripts/test/parser-metrics-contract.test.js` | 2 passed | PASS |
| TC-3302, TC-3303, TC-3306 | `node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests/test_parser_metrics.py apps/worker/tests/test_context_parser.py` | 7 passed; existing pytest cache-permission warning only | PASS |
| TC-3306 | `npm test` | Records 6, contracts 90, Web 18, API 149 passed/33 skipped, Worker 33 passed | PASS |
| TC-3307 | `npm run lint`; `npm run typecheck`; `npm run build`; `git diff --check` | All lint, strict type checks, builds and diff checks passed | PASS |
| TC-3307 | `npm run validate` | Architecture validation passed 22/22 after final records were completed | PASS |

## Notes

- No hosted or external metrics backend is claimed by this increment.
- Existing warnings: Windows pytest cache-permission warnings and the existing Starlette/httpx
  deprecation warning; no test failure resulted.

## Final Status

**Final status:** PASS
