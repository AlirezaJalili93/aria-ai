# Test Report: 0081 Generation Lock Role Migration Safety

- **Increment ID:** `0081-generation-lock-role-migration-safety`
- **Environment:** Windows 11, PostgreSQL 16 isolated Docker cluster, Node.js contract tests
- [Development record](./development.md)

## Environment

Local Windows PowerShell, PostgreSQL 16 disposable Docker cluster and repository-pinned runtimes.
Final regression verification: 2026-09-29.

## Test Cases

| ID | Scenario | Expected | Actual | Status |
| --- | --- | --- | --- | --- |
| TC-8101 | Two empty databases run the full migration chain in one cluster | Both reach head and share one compatible Role | Both reached `0030`; exact Role attributes verified | PASS |
| TC-8102 | Existing Role has an incompatible least-privilege attribute | Migration fails before database-local 0030 objects | `LOGIN` Role rejected; `aria_internal` absent after rollback | PASS |
| TC-8103 | Downgrade first then last migrated database | First preserves shared Role; last removes it | Shared Role/helpers preserved, then unused Role removed | PASS |
| TC-8104 | Static privilege and migration contract | No runtime privilege/helper/RLS expansion | Conditional validation and dependency-aware cleanup verified | PASS |
| TC-8105 | Repository regression gates | `npm test` and `npm run validate` pass | Full gates passed | PASS |

## Execution Results

- `node --test scripts/test/generation-lock-role-migration-contract.test.js` → 2 passed.
- `npm run test:generation-lock-role-migration` →
  `GENERATION_LOCK_ROLE_MIGRATION_GATE=PASS` against a disposable PostgreSQL 16 container.
- `npm run lint` → PASS.
- `npm run typecheck` → PASS; API 164 and Worker 69 source files checked.
- `npm run build` → PASS.
- `npm test` → PASS; CI contract 189, Eval 35 and Web 40 passed. Without
  `TEST_DATABASE_URL`, API reported 456 passed/155 skipped and Worker 163 passed/25 skipped.
  These skips are not PostgreSQL integration evidence; the configured run is recorded below.
- Configured PostgreSQL API run → 610 passed, 1 Hosted-only skip.
- Configured PostgreSQL Worker run with explicit `postgresql+asyncpg` URL → 187 passed,
  1 Redis skip. The omitted Redis test was then run separately with
  `TEST_QUEUE_BROKER_URL` → 1 passed; all 188 Worker cases have passing evidence.
- `npm run validate` → PASS, 23 checks after correcting the required report headings.
- `npm run scan:secrets` → PASS, 953 publishable text files.

## Failures and Corrections

- The first configured Worker run used a plain `postgresql` URL in a test that directly creates
  an async engine; it attempted to load the absent synchronous `psycopg2` driver. Re-running with
  the explicit `postgresql+asyncpg` test URL passed without changing code or dependencies.
- The documentation validator initially rejected missing `Environment` and `Execution Results`
  headings. The report now follows the required template and validation passes.
- Capturing the expected Alembic rejection through Windows PowerShell initially treated native
  stderr as a terminating error. The runner now captures the exit code and verifies the exact
  expected rejection message before declaring the negative test passed.

The first sandboxed lint/typecheck/build attempt could not open the user-level `uv` cache and was
an environmental permission failure, not a code failure. The same commands passed unchanged with
the required filesystem access. The disposable Docker container was removed by the test runner.

## Security and Privacy

The test cluster contains schema-only synthetic state. No customer data, credential, content or
secret is logged.

## Final Status

**Final status:** PASS
