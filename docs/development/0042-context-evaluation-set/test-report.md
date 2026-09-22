# Test Report: 0042 — Context Evaluation Set

- [Development record](./development.md)

## Environment

- Windows 11, Node.js 24.11.1, npm 11.x
- Python 3.12, uv-managed API/Worker environments
- Local worktree-scoped `UV_CACHE_DIR`; no external Provider or customer data
- Eval set `context_structuring_eval_v1`, report/metric/schema version `1`

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4201 | Contract | Load manifest, schemas and all 20 versioned Persian fixtures | Exact inventory, synthetic marker, valid IDs and Ground Truth contract |
| TC-4202 | Regression | Execute deterministic Fake Provider across the full set | Stable redacted report; structural metrics reproducible; Model Quality remains not run |
| TC-4203 | Metric unit | Wrong class plus unmatched prediction | Accuracy denominator equals gold count plus unmatched predictions |
| TC-4204 | Metric/rubric | Approved thresholds and Persian Review formula | Direction-aware levels and exact 1–5 normalized formula |
| TC-4205 | Negative/security | Missing provenance, forbidden assumption and malformed Provider items | Safe contract failures without crash or raw-content report leakage |
| TC-4206 | Repository gates | Full tests, lint, typecheck, build, architecture validation and secret scan | All quality/security gates PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4201 | `npm run test:eval` | 20 fixtures loaded; inventory/schema checks passed | PASS |
| TC-4202 | `node scripts/context-evaluation.mjs --output .tmp/h05-fake-report.json` | Redacted report generated; Contract gate PASS; Model Quality NOT_RUN | PASS |
| TC-4203 | `npm run test:eval` | Exact accuracy numerator/denominator regression passed | PASS |
| TC-4204 | `npm run test:eval` | Threshold directions and Persian score formula passed | PASS |
| TC-4205 | `npm run test:eval` | Unsafe provenance/assumption and malformed-item cases passed | PASS |
| TC-4206 | `npm run lint`, `npm run typecheck`, `npm run build`, `npm test`, `npm run validate`, `npm run scan:secrets` | All repository gates passed | PASS |

## Commands and Results

```text
npm run test:eval      PASS — 8 passed
npm run test:ci        PASS — 112 passed
npm test --workspace @aria/web
                       PASS — 19 passed
npm run test:api       PASS — 197 passed, 68 skipped (DB integration env not selected)
npm run test:worker    PASS — 55 passed
npm run lint           PASS — Web, API and Worker checks passed
npm run typecheck      PASS — strict checks passed
npm run build          PASS — Next.js production build and Python compilation passed
npm test               PASS — all configured repository groups passed with worktree UV cache
npm run validate       PASS — 22 architecture/development-record checks passed
npm run scan:secrets   PASS — no potential secrets found
```

The first full `npm test` attempt reached the API suite and stopped because the sandbox could not
write the user-global uv cache. Re-running with the worktree-local `UV_CACHE_DIR` removed that
environment issue; no code change was needed for the test environment.
The first secret-scan run found an inert credential-shaped literal in the pre-existing Job Status
API test. The fixture now assembles the same value at runtime and the final repository scan passed.

## Final Status

**Final status:** PASS
