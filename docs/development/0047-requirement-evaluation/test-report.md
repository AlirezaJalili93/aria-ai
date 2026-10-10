# Test Report: 0047 — Requirement Extraction Evaluation

- [Development record](./development.md)

## Environment

- Windows 11, Node.js 24.x, npm 11.x
- Deterministic Fake Provider only; no network or customer data

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4701 | Dataset | Load manifest and fixture inventory | Exactly immutable IDs `fa_req_001..020`; Persian synthetic coverage |
| TC-4702 | Alignment | Match candidates and duplicate groups | Annotation-driven only; no fuzzy/LLM matching |
| TC-4703 | Metrics | Pooled recall, omission, unsupported detection/output and duplicate counts | Frozen formulas and denominators exactly reproduced |
| TC-4704 | Gate | Threshold boundaries, `N/A`, empty output and item-level critical misses | Exact target/minimum/fail/blocker semantics |
| TC-4705 | Human review | Reviewer agreement and difference-at-least-two disagreement | Mean or mandatory adjudicated score per dimension |
| TC-4706 | Provider | Run deterministic Fake Provider | Contract Gate may pass; Model Quality Gate remains not-run |
| TC-4707 | Privacy | Serialize report and inspect harness output | No Context, Gold/generated text, Source References, prompt/response or reviewer notes |
| TC-4708 | Full gates | Tests, lint, typecheck, build, validate and secret scan | Every mandatory gate PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4701 | Focused Node contract suite | Manifest and exact stable 20-Fixture inventory verified | PASS |
| TC-4702 | Focused Node contract suite | Annotation-only matching and duplicate groups verified | PASS |
| TC-4703 | Focused Node contract suite | Pooled formula outputs reproduced exactly | PASS |
| TC-4704 | Focused Node contract suite | Threshold boundaries, critical blockers and `N/A` verified | PASS |
| TC-4705 | Focused Node contract suite | Two-reviewer and adjudication rules verified | PASS |
| TC-4706 | Focused Node contract suite | Fake Contract Gate passed; Model Quality remained not-run | PASS |
| TC-4707 | Focused Node contract suite + secret scan | Prohibited Eval content absent from report/log surface | PASS |
| TC-4708 | Repository quality gates | Tests, lint, typecheck, build, validate, secret scan and diff check passed | PASS |

## Commands and Results

```text
node --test scripts/test/requirement-evaluation-contract.test.js
PASS — 16 tests

npm run test:eval
PASS — 24 tests (8 Context Eval + 16 Requirement Eval)

npm test
PASS — records 6; CI/contracts 122; Eval 24; Web 26; API 256 passed / 91 skipped;
Worker 57. The API skips are the existing PostgreSQL integration cases gated by
`TEST_DATABASE_URL`; one existing Starlette deprecation warning was reported.

npm run lint
PASS

npm run typecheck
PASS

npm run build
PASS

npm run validate
PASS

npm run scan:secrets
PASS — 571 publishable text files inspected

git diff --check
PASS
```

## Final Status

**Final status:** PASS

The deterministic Fake Provider result is Contract/Regression evidence only. Real-provider Model
Quality execution and its human-review scores remain intentionally not run until G02/G03.
