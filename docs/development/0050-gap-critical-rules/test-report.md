# Test Report: 0050 — Gap Critical Rules

- **Increment:** S1-J02-B
- **Date:** 2026-09-09
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Python 3.12 environment managed by repository `uv` runner
- PostgreSQL 16 Alpine in local Docker Desktop
- Dedicated temporary database: `aria_j02b_test_20260909`
- Fake deterministic AI objects only; no real Provider or customer data
- Temporary database was dropped after verification; readback confirmed zero matching databases.

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-5001 | Contract | Exact Landing/Corporate/Portfolio Matrix | IDs and Critical flags equal approved v1 |
| TC-5002 | Unit | Signal origin, shape, coverage and Snapshot support | Invalid/untrusted claims rejected |
| TC-5003 | Unit | Missing Critical/non-Critical Checklist items | Only approved Critical item matches CGR-001 |
| TC-5004 | Unit | Conflict over two Requirements with/without `must` | CGR-002 follows exact Key predicate |
| TC-5005 | Unit | Proposed assumption in three sensitive domains | CGR-003 matches; invalid subject rejects |
| TC-5006 | Unit/Integration | Rule Match without Candidate | Immutable-template Critical Gap generated |
| TC-5007 | Application | Model Critical without Rule Match | Stored as High; not authoritative |
| TC-5008 | Unit | Multiple rule matches | Stable CGR-003/002/001 ordering; no match loss |
| TC-5009 | PostgreSQL | Successful Job metadata and replay | Versions/counts pinned; no second AI/Usage call |
| TC-5010 | Contract/Integration | Invalid policy/signal/duplicate/Snapshot/DB | Fail closed and no partial business writes |
| TC-5011 | Quality | Repository test/lint/type/build/docs/secret gates | All required gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
| --- | --- | --- | --- |
| TC-5001–TC-5008 | Focused Python and Node contract tests | 21 Application/Rule + 8 Node PASS | PASS |
| TC-5009–TC-5010 | Focused PostgreSQL J02 suite | 11 PostgreSQL tests; combined 32 PASS | PASS |
| TC-5011 | `npm run lint` | Web ESLint + API/Worker Ruff PASS | PASS |
| TC-5011 | `npm run typecheck` | Web TypeScript + API 116 Python files + Worker 26 files PASS | PASS |
| TC-5011 | `npm run test:ci` | 134/134 PASS | PASS |
| TC-5011 | `npm run test:eval` | 24/24 PASS | PASS |
| TC-5011 | `npm run test:web` | 26/26 PASS | PASS |
| TC-5011 | `TEST_DATABASE_URL=... npm run test:api` | 407/407 PASS | PASS |
| TC-5011 | `npm run test:worker` | 57/57 PASS | PASS |
| TC-5011 | `npm run build` | Next.js/API/Worker production build PASS | PASS |
| TC-5011 | `npm test` | Records 6; CI 134; Eval 24; Web 26; API 407; Worker 57 — all PASS | PASS |
| TC-5011 | `npm run validate` | 22/22 architecture checks PASS | PASS |
| TC-5011 | `npm run scan:secrets`; `git diff --check` | 602 files scanned; no secret or whitespace error | PASS |

## Failures and Corrections

- Direct `python` was unavailable; used the repository's pinned `uv` runner.
- Default user-level uv cache was sandbox-inaccessible; redirected `UV_CACHE_DIR` to this worktree.
- Interim review found Rule processing followed provider order; corrected it to the approved stable
  CGR-003/002/001 order.
- Interim review found a Signal could point at an unrelated Candidate; added type and exact
  Requirement-set consistency validation.
- Final review found replay counters were not checked against persisted rows; added corruption and
  upper-bound validation plus a PostgreSQL regression test.
- The test runner reported the existing Starlette/httpx deprecation warning and non-fatal local
  Pytest cache permission warnings; neither affected execution or product behavior.

## Final Status

**Final status:** PASS
