# Test Report: 0075 — Scope Generation Runtime Foundation

- **Status:** PASS — controlled synthetic-only runtime foundation
- [Development record](./development.md)

## Environment and Commands

- Windows, Python 3.12, Node.js 24.x, npm 11.x, Docker Desktop PostgreSQL 16.
- Isolated database `aria_0075_test`; migration head `0029_scope_generation_runtime`.
- Deterministic Fake AI-05 and synthetic fixtures only; no paid Provider or customer content.
- `npm run test:scope-generation-runtime`: 4 passed.
- Full database-backed API: 605 passed, 1 skipped; Worker: 182 passed, 1 skipped before the
  additional post-AI input-change test; focused Worker PostgreSQL tests: 5 passed afterward.
- Fresh Alembic upgrade to head, downgrade to 0028 and re-upgrade to 0029: PASS.
- `SET ROLE aria_worker` and full Worker runtime: PASS with no broad input-table UPDATE grant.
- `npm run test:ci`: 185 passed; `npm run test:eval`: 35 passed; `npm run test:web`: 40 passed.
- `npm run lint`, `npm run typecheck`, `npm run build`, `npm run scan:secrets`: PASS.
- `npm test`: PASS — default API 454 passed/152 skipped; Worker 163 passed/21 skipped;
  increment contracts, CI, Eval and Web passed. Database-backed suites above supplied the
  missing PostgreSQL evidence.
- `npm run validate`: PASS — 23 architecture and development-record checks.
- `git diff --check`: PASS; Git emitted only the existing Windows LF/CRLF conversion notices.

## Test Cases

| Case | Expected | Actual | Result |
| --- | --- | --- | --- |
| TC-7501 | Empty eligible Requirements reject before AI/Usage | Application and PostgreSQL tests reject before invocation, ledger or persistence | PASS |
| TC-7502 | Empty eligible Context rejects before AI/Usage | Application test rejects with zero AI and Usage | PASS |
| TC-7503 | Open Critical Gap blocks; dismissed does not | PostgreSQL scheduler blocks open Critical, allows dismissed | PASS |
| TC-7504 | Existing Draft and active Job conflicts | Application Draft guard and PostgreSQL partial unique Job index reject duplicates | PASS |
| TC-7505 | Draft + Job success commit or roll back together | Forced commit failure leaves zero Draft and running Job; same Job recovers | PASS |
| TC-7506 | Job/Outbox and identifier-only Queue delivery | One atomic pair; publisher emits exactly three identifiers to canonical task | PASS |
| TC-7507 | Synthetic-only Worker; no hosted/public path | Worker role executes Fake path; task absent from hosted composition | PASS |
| TC-7508 | Pinned input mismatch fails with stable code | Pre-AI and post-AI edits yield `SCOPE_GENERATION_INPUT_CHANGED`; no Draft | PASS |
| TC-7509 | Full repository quality gate | Test, lint, typecheck, build, secret scan and validation | PASS |

## Execution Results

| Case | Evidence | Actual result | Status |
| --- | --- | --- | --- |
| TC-7501–TC-7503 | API Application and PostgreSQL tests | Preconditions and K02 policy enforced before Fake AI | PASS |
| TC-7504–TC-7506 | API/Worker PostgreSQL, publisher and contract tests | Durable identity, uniqueness and atomic boundaries verified | PASS |
| TC-7507–TC-7508 | Worker-role PostgreSQL and leak-negative tests | Synthetic-only path; no content in logs/Queue; changed input fails closed | PASS |
| TC-7509 | Local quality commands | Full gate results listed above and below | PASS |

## Skips and Limitations

- Default suites without `TEST_DATABASE_URL` skip PostgreSQL tests; the full DB-backed API and
  Worker suites above closed the previous 151/16 DB skips for this local environment.
- The default API suite emitted a non-blocking Starlette/httpx deprecation warning; both default
  Python suites emitted non-blocking Windows pytest-cache permission warnings. Isolated DB runs
  disabled pytest cache and passed.
- One Hosted-upload API test and one Redis Worker test remain environment-gated. Neither is
  counted as PASS or as evidence for Hosted activation.
- The local PostgreSQL fixture does not define `aria_api`; migration adds no direct API Draft-write
  grant. Worker named INSERT is allowed, Worker UPDATE/DELETE are denied and Draft RLS is enabled
  (`t|f|f|t` in the final privilege projection).
- Fake Provider PASS verifies orchestration and safety only, not real-model quality.

## Final Status

**Final status:** PASS

PASS for the internal controlled 0075 synthetic foundation. Public, customer, paid Provider and
Hosted activation remain NO-GO until separate approved release gates. The final `npm test`,
`npm run validate` and `git diff --check` runs all passed.
