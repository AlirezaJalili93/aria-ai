# Test Report: 0095 Generation Output Contract

- Increment ID: `0095-generation-output-contract`
- Date: 2026-10-10
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Synthetic Persian fixtures only
- Customer content / real Provider / hosted execution: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9501 | REQ-9501, REQ-9502 | Registry has exactly fourteen complete, immutable Component contracts | PASS |
| TC-9502 | REQ-9501, REQ-9503 | Candidate excludes IDs/protection; canonical schema requires them | PASS |
| TC-9503 | REQ-9502, REQ-9504, REQ-9505, REQ-9506, REQ-9507 | Structural and business validation fails closed | PASS |
| TC-9504 | REQ-9503, REQ-9508 | Application adds unique IDs and initial protection without mutating candidate | PASS |
| TC-9505 | REQ-9504, REQ-9508 | Exact Asset authorization is required before finalizer | PASS |
| TC-9506 | REQ-9505 | Navigation and Requirement references resolve only within pinned sets | PASS |
| TC-9507 | REQ-9506 | SimpleForm rejects network action and invalid/duplicate bounded fields | PASS |
| TC-9508 | REQ-9507 | LF normalization works only for multiline and content never enters errors | PASS |
| TC-9509 | REQ-9508 | Finalizer failure leaves no successful in-memory artifact | PASS |
| TC-9510 | all | Full repository test and validation gates pass | PASS |

## Commands and Results

```text
npm run test:generation-output
PASS — 4 tests

pytest apps/api/tests/test_generation_ast_contract.py
PASS — 15 tests

Ruff focused validation
PASS

Mypy focused validation
PASS

npm test
PASS — Records 6; Generation Output 4; CI 213; Eval 35; Web 47;
       API 543 passed / 175 environment-gated skipped;
       Worker 208 passed / 36 environment-gated skipped

npm run lint
PASS — Web ESLint; API and Worker Ruff

npm run typecheck
PASS — Web, API and Worker type checks

npm run build
PASS — production Web/API/Worker build

npm run validate
PASS — repository validation completed
```

## Security and Leakage Evidence

- Provider-supplied identity/protection, unknown fields, remote URLs and invalid Asset/reference
  values are rejected before the finalizer.
- Asset authorization receives only Account, Project and UUID references; no remote fetch path is
  present.
- Stable errors contain reason codes only and tests assert that injected URL/content is absent.
- SimpleForm has no action/endpoint/network field and remains `preview_only`.

## Execution Results

- All three synthetic Project Types passed validation, Asset authorization, Application enrichment
  and one finalizer call; together they exercise all fourteen Registry Components.
- Negative mutations for Provider-owned identity, incompatible responsive rules, missing media,
  missing alt text, unresolved navigation, remote URLs and unpinned Requirements failed closed.
- Unauthorized Assets prevented finalization and a synthetic finalizer failure exposed no partial
  successful artifact.
- Full repository tests, static analysis, production build and architecture validation passed; the
  recorded API/Worker skips remain environment-gated integration coverage rather than failures.

## Final Status

**Final status:** PASS
