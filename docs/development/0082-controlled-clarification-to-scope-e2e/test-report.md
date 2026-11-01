# Test Report: 0082 Controlled Clarification to Scope E2E

- **Increment ID:** `0082-controlled-clarification-to-scope-e2e`
- **Environment:** Windows 11, PostgreSQL 16 and Redis 7 local Docker services, repository-pinned runtimes
- [Development record](./development.md)

## Environment

Local Windows PowerShell, a dedicated `aria_0077_test_0082` PostgreSQL database, local Redis DB 15,
and repository-pinned API/Worker/Web runtimes. Final verification: 2026-09-29.

## Test Cases

| ID | Scenario | Expected | Actual | Status |
| --- | --- | --- | --- | --- |
| TC-8201 | Synthetic explicit AI-01 → AI-02 → AI-03 → Clarification → AI-05 | One resolved Gap and one successful Scope Draft | `CONTROLLED_0082_E2E=PASS` | PASS |
| TC-8202 | Two questions created upfront; answer Question 1 then Question 2 | Gap open after first answer and resolved only after second | All Critical Gaps followed the frozen sequence | PASS |
| TC-8203 | AI-05 before and after full Clarification resolution | Blocked with zero effects before; explicit command succeeds after | Two blocked checks had unchanged counters; final Job succeeded | PASS |
| TC-8204 | Answer propagation boundary | No Context/Requirement/version mutation and no answer text in AI-05 input | Exact snapshots equal; payload and Draft leakage checks passed | PASS |
| TC-8205 | Replay, invalid input, tenant isolation and leakage | Fail closed with no duplicate or sensitive output | Replay, empty input, foreign Tenant and log checks passed | PASS |
| TC-8206 | PostgreSQL negative/recovery suites | Replay, pinning, rollback and tenant cases pass | API 9 and Worker 9 passed | PASS |
| TC-8207 | Repository regression gates | `npm test` and `npm run validate` pass | Full gates passed | PASS |

## Execution Results

- `npm run test:clarification-to-scope-e2e` → `CONTROLLED_0082_GATE=PASS`; controlled E2E PASS,
  API PostgreSQL 9 passed and Worker PostgreSQL 9 passed.
- `node --test scripts/test/clarification-to-scope-e2e-contract.test.js` → 3 passed.
- `npm run lint` → PASS.
- `npm run typecheck` → PASS; API 164 and Worker 69 source files checked.
- `npm run build` → PASS; Next.js production build and Python compile gates passed.
- `npm test` → PASS; CI contract 192, Eval 35 and Web 40 passed. The unconfigured
  aggregate API run reported 456 passed/155 skipped and Worker 163 passed/25 skipped; those skips
  are not used as PostgreSQL evidence, which comes from the configured 0082 Gate above.
- `npm run validate` → PASS.

## Failures and Corrections

- The first controlled run failed on the sixth Clarification insert with PostgreSQL `42P10`.
  SQLAlchemy had parameterized the `ON CONFLICT` partial-index predicate; after five executions,
  asyncpg/PostgreSQL selected a generic plan that could not infer the partial unique index. The
  repository now emits the literal predicate from migration 0016, and two clean controlled runs
  passed afterward.
- The first static contract rerun still expected an earlier draft filename for the Clarification
  PostgreSQL suite. It was corrected to the existing `test_clarification_postgres.py` path.
- Pytest emitted non-fatal warnings because local ACLs prevented `.pytest_cache` creation.

## Security and Privacy

Only versioned synthetic Persian fixtures are permitted. Question text, answer text, Context,
Requirement, Gap and Scope content must not appear in logs, metric labels or queue envelopes.

## Final Status

**Final status:** PASS
