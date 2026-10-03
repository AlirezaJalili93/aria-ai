# Test Report: 0036 Limited Provider-Neutral Routing Policy Contract

- Increment ID: `0036-limited-routing-policy-contract`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

- Windows workspace, PowerShell
- Node/npm repository toolchain
- Python 3.12 worker environment managed through `uv`
- `UV_CACHE_DIR` set to the workspace `.uv-cache` for reproducible local execution
- No external Provider, SDK, credential or network dependency used

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3601 | Unit | Construct each canonical routing tier | `cheap`, `standard`, and `premium` are accepted; unknown tier is rejected |
| TC-3602 | Unit/Contract | Resolve an opaque task type with a supplied policy | Policy returns a `RoutingDecision`; no task vocabulary or mapping is required |
| TC-3603 | Unit | Resolve without a policy | Explicit `routing_policy_required` error; no default tier |
| TC-3604 | Contract | Inspect Application routing boundary | No Provider/model/SDK, mapping, default, escalation or fallback is introduced |
| TC-3605 | Regression | Run repository test and quality gates | Existing and new tests remain green; documentation convention remains enforced |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-3601 | `node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests/test_routing_policy.py` | 6 passed | PASS |
| TC-3602 | Same focused pytest command | Opaque task/context passed through a fixed policy; decision returned | PASS |
| TC-3603 | Same focused pytest command | Missing policy raised `routing_policy_required` | PASS |
| TC-3604 | `node --test scripts/test/routing-policy-contract.test.js` | 2 contract tests passed | PASS |
| TC-3605 | `npm test` | Records 6 passed; contracts 96 passed; Web 18 passed; API 149 passed/33 skipped; Worker 53 passed | PASS |
| TC-3605 | `npm run lint; npm run typecheck; npm run build; npm run validate; git diff --check` | All commands passed; diff check reported only existing CRLF conversion warnings | PASS |

## Failures and Corrections

The first contract-test run used an inverted assertion against the ADR text and failed. The test was
corrected to assert that the ADR explicitly records each non-decision. The focused suite then passed.
The first uv invocation encountered the existing Windows cache-permission issue; subsequent commands
used the workspace-local `UV_CACHE_DIR` and passed. The first architecture validation run also
correctly rejected this report while it was `PENDING`; the report was finalized before the final
quality run. Pytest may still emit its existing local `.pytest_cache` permission warning; it does not
affect test results.

## Final Status

**Final status:** PASS
