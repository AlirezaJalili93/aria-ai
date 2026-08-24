# Test Report: 0016 Membership Resolution

- Increment ID: `0016-membership-resolution`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Python 3.12 project runtime through repository-pinned uv
- PostgreSQL integration through `TEST_DATABASE_URL` when available
- Node.js 24.11.1 / npm 11

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1601 | Unit | Select one Account from two active Memberships | Requested Membership and persisted Role are returned |
| TC-1602 | Unit | Select invited or suspended Membership | Both states are denied with `ActiveMembershipRequired` |
| TC-1603 | Contract | Inspect Application use case | No Header, Cookie, Session, FastAPI, or transport contract exists |
| TC-1604 | Unit | Select Account without subject Membership | Selection is denied without fallback to another active Account |
| TC-1605 | Contract | Inspect Application and Infrastructure boundaries | Application is provider/framework neutral; SQLAlchemy remains in Infrastructure |
| TC-1606 | PostgreSQL integration | Resolve selected active Membership among Tenant A/B fixtures | Correct subject+Account row and DB Role are returned without writes |
| TC-1607 | PostgreSQL integration | Resolve invited/suspended Membership | Both persisted states are denied |
| TC-1608 | Repository validation | Run architecture and record gates | Modular-monolith structure and linked records pass |
| TC-1609 | Schema/query contract | Inspect M001 unique constraint and resolver predicate | Existing `(account_id,user_id)` index covers the equality lookup; no migration added |
| TC-1610 | Regression | Run aggregate test suite | Existing Web/API/Worker/CI behavior remains passing |
| TC-1611 | Unit/Security | Adapter returns an active Membership for mismatched subject or Account | Application fails closed with a projection invariant error |
| TC-1612 | Contract/Quality | Dependency audit populates Git-ignored `.data` cache with third-party Markdown | Validator excludes generated local data and continues checking repository Markdown |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-1601, TC-1602, TC-1604, TC-1611 | `pytest -q apps/api/tests/test_membership_resolution.py` | 6 passed | PASS |
| TC-1603, TC-1605, TC-1609, TC-1612 | `node --test scripts/test/membership-resolution-contract.test.js` | 5 passed | PASS |
| TC-1606, TC-1607 | PostgreSQL 18 on `127.0.0.1:55432`; `pytest -q apps/api/tests/test_account_bootstrap_postgres.py` | 10 passed, including 3 S1-B03 database cases; temporary server stopped | PASS |
| TC-1608 | `npm run validate` | Architecture/development-record checks passed | PASS |
| TC-1610 | `npm run lint` | Web ESLint and API/Worker Ruff passed | PASS |
| TC-1610 | `npm run typecheck` | Web TypeScript and API/Worker MyPy passed | PASS |
| TC-1610 | `npm run test:ci` | 36 passed | PASS |
| TC-1610 | `npm run test:web` | 4 passed | PASS |
| TC-1610 | `npm run test:api` | 83 passed with PostgreSQL integration enabled | PASS |
| TC-1610 | `npm run test:worker` | 16 passed | PASS |
| TC-1610 | `npm run build` | Next.js production build and Python compile checks passed | PASS |
| TC-1601–TC-1612 | `npm test` | 146 passed across records, contracts, Web, API, and Worker | PASS |
| TC-1608, TC-1610 | `npm run scan:dependencies` | npm, API, and Worker audits found no blocking vulnerabilities | PASS |
| TC-1608, TC-1610 | `npm run scan:secrets` | 186 publishable text files inspected; no secret material found | PASS |

## Failures and Corrections

- Initial Python commands could not access the user-global uv cache. Execution was corrected to use
  ignored project-local `UV_CACHE_DIR`.
- uv attempted to synchronize a locked Windows virtual environment. The already synchronized pinned
  environment was used with `UV_NO_SYNC=1`; lint, MyPy, tests, and builds then passed.
- The first dependency audit could not access the user-global uv tool lock. The pinned `pip-audit`
  execution was moved to a project-local ignored `UV_TOOL_DIR` and rerun with approved network
  access; npm, API, and Worker audits then passed with no blocking vulnerabilities.
- Sandboxed `initdb` could not create its Windows restricted token. The approved PostgreSQL 18 binary
  was run outside the sandbox against a project-local, loopback-only temporary cluster; all database
  tests passed and the server was stopped.
- Senior review found that the Application should independently reject a mismatched adapter result.
  The fail-closed invariant and TC-1611 were added before the final aggregate run.
- After the dependency audit populated its local cache, architecture validation traversed ignored
  third-party Markdown and reported two irrelevant broken links. The walker now excludes the
  Git-ignored `.data/` root, TC-1612 locks the correction, and repository Markdown validation remains
  enabled for every publishable path.

## Final Status

**Final status:** PASS
