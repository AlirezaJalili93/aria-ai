# Test Report: 0076 — Synthetic Runtime Tenant Isolation

- **Status:** PASS — local synthetic-runtime tenant isolation
- [Development record](./development.md)

## Environment

- Windows, Python 3.12, Node.js 24.x, PostgreSQL 16 in Docker Desktop.
- Isolated local `aria_0075_test` database at migration head 0029.
- Synthetic fixture content only; no real Provider, customer data or hosted service.

## Test Cases

| Case | Expected | Actual | Result |
| --- | --- | --- | --- |
| TC-7601 | Both Tenant A and Tenant B exist concurrently | Two Account and Project rows in each fixture | PASS |
| TC-7602 | AI-02/03/05 foreign and missing Project resolve identically; no Job/Outbox write | Three PostgreSQL parameter cases returned the same context-required error; zero writes | PASS |
| TC-7603 | AI-02/03/05 forged foreign Outbox cannot prepare Tenant A Job | Three PostgreSQL parameter cases rejected the Outbox reference | PASS |
| TC-7604 | Rejected attempts leave Job queued/unchanged and no generated effects | `queued`, attempt count zero, no Requirement/Gap/Draft | PASS |
| TC-7605 | `npm test`, `npm run validate`, lint and diff check pass | Final repository gate recorded below | PASS |

## Commands and Results

- Focused PostgreSQL API suite: 3 passed.
- Focused PostgreSQL Worker suite: 3 passed under `aria_worker` after the final no-effect
  assertion.
- Full PostgreSQL API suite: 608 passed, 1 skipped.
- Full PostgreSQL Worker suite: 186 passed, 1 skipped, using an explicit `postgresql+asyncpg://`
  test URL. The first Worker run used a URL without the async driver and one existing usage-ledger
  test could not import `psycopg2`; this was an environment-command error, not a code failure.
- `npm run lint`: PASS.
- `npm test`: PASS. Default API: 454 passed/155 skipped; Worker: 163 passed/24 skipped.
  The focused and full database-backed runs above supply evidence for the six new cases.
- `npm run validate`: PASS after adding the required execution-results section.
- `git diff --check`: PASS; Git displayed only pre-existing LF/CRLF conversion notices.

## Execution Results

| Case | Evidence | Status |
| --- | --- | --- |
| TC-7601–TC-7602 | Real PostgreSQL API parameterized suite, 3 passed | PASS |
| TC-7603–TC-7604 | Real PostgreSQL Worker parameterized suite, 3 passed | PASS |
| TC-7605 | Full `npm test`, lint, architecture validation and diff check | PASS |

## Skips and Limitations

- Default `npm test` without `TEST_DATABASE_URL` skips DB-backed cases; focused runs must
  supply the isolated local URL and are reported separately.
- The default suites' other environment-gated tests remain skipped; this report does not
  convert those skips to PASS. Windows pytest-cache warnings and one Starlette/httpx
  deprecation warning did not affect the passing test results.
- This is a narrow regression extension, not evidence for Hosted or real-Provider release.

## Final Status

**Final status:** PASS for this local two-Tenant security regression only. Full Product/Hosted AI
activation remains blocked by its separate approved gates.
