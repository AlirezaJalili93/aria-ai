# Test Report: 0030 Worker Idempotency Foundation

[Development record](./development.md)

## Environment

- Windows 11 host, repository worktree `staging-migrations`
- Python 3.12 Worker environment managed by `uv`
- Node.js/npm repository toolchain
- Fake guard repository only; no Queue ACK/requeue or PostgreSQL lock strategy was exercised.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3001 | Contract | Inspect Worker guard boundary | Provider-neutral port uses `job_id` and approved acquisition outcomes |
| TC-3002 | Unit | `already_in_progress` duplicate delivery | Handler is not called; duplicate is suppressed |
| TC-3003 | Unit | `already_completed` duplicate delivery | Handler is not called; result is successful no-op |
| TC-3004 | Recovery abstraction | Handler interruption then fixture recovery | Completion is not recorded on interruption; fixture recovery executes once |
| TC-3005 | Observability | Inspect Worker guard events | Required event names and safe IDs/context are present; payload is absent |
| TC-3006 | Scope/Architecture | Inspect imports and deferred boundaries | No DB schema, lock, timeout, retry, ACK/requeue or artifact policy is invented |
| TC-3007 | Worker regression | Run all Worker tests | Existing Celery runtime and bootstrap behavior remains green |
| TC-3008 | Repository gate | Run full npm test | Records, contracts, Web, API and Worker suites pass |
| TC-3009 | Quality | Run lint, typecheck, build and validate | All quality gates pass |

## Execution Results

| ID | Command | Actual | Status |
|---|---|---|---|
| TC-3001, TC-3005, TC-3006 | `node --test scripts/test/worker-idempotency-contract.test.js` | 3 contract tests passed | PASS |
| TC-3002–TC-3004 | `node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests/test_job_execution.py` | 4 tests passed | PASS |
| TC-3007 | `node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests` | 26 passed | PASS |
| TC-3008 | `npm test` | 6 record tests, 84 contracts, 18 Web, 146 API/33 skipped, 26 Worker passed | PASS |
| TC-3009 | `npm run lint`; `npm run typecheck`; `npm run build`; `npm run validate` | All passed; architecture validation 22/22 | PASS |

## Notes

- No PostgreSQL claim/lock or real Queue runtime evidence is claimed; both are explicitly deferred by
  ADR-017.
- Warnings were limited to existing Windows pytest cache permissions and the existing Starlette/httpx
  deprecation notice.

## Final Status

**Final status:** PASS
