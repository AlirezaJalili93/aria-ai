# Test Report: 0019 Architecture Hardening

- Increment ID: `0019-architecture-hardening`
- Date: 2026-09-01
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Repository-pinned Node.js/npm and Python 3.12/uv runtimes
- Real PostgreSQL integration target when `TEST_DATABASE_URL` is available

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1901 | Contract/Security | Inspect M001a downgrade | No `GRANT`; downgrade never broadens Data API/default privileges |
| TC-1902 | PostgreSQL | Grant roles, upgrade, downgrade, re-upgrade | Hardening remains fail-closed throughout reversible schema flow |
| TC-1903 | Contract | Inspect Bootstrap dependency | No broad `except Exception`; only declared failures map to stable 503 |
| TC-1904 | API | Declared vs unexpected Bootstrap failures | Declared infrastructure/invariant failures map safely; programming error remains 500 |
| TC-1905 | Contract | Inspect Tenant dependency chain | JWT verification feeds Membership resolver directly; no Bootstrap dependency |
| TC-1906 | API | Tenant request | Exactly one Membership resolution and zero Bootstrap calls |
| TC-1907 | Web | Render authenticated `/projects` | Page does not call Bootstrap a second time |
| TC-1908 | Database/Application | Insert and update mutable rows | Documented `updated_at` owner advances the value consistently |
| TC-1909 | Web/Logging | Auth event emission | Versioned safe schema; no Email/JWT/callback query/secret fields |
| TC-1910 | Web | Callback failures | Safe internal reason codes distinguish invalid callback, Auth service, and Bootstrap failure |
| TC-1911 | Regression | Full repository gates | `npm test` and `npm run validate` pass |
| TC-1912 | Contract | Inspect ADR-009/ADR-011 separation | Bootstrap returns no Account data; discovery is read-only, active-only and pre-tenant |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/architecture-hardening-contract.test.js scripts/test/project-domain-contract.test.js` | 8 passed, including P1 and Account Discovery separation contracts | PASS |
| `npm run test:web` | 12 passed; duplicate Bootstrap, structured events and callback reason classes verified | PASS |
| `npm run test:api` with real `TEST_DATABASE_URL` | 121 passed; declared/unexpected Bootstrap mapping and Tenant separation included | PASS |
| `npm run build` | Next.js production build plus API/Worker compile completed | PASS |
| `npm run scan:secrets` | 239 publishable text files inspected; no secret finding | PASS |
| `npm run scan:dependencies` | npm/API/Worker scans found no blocking vulnerability | PASS |
| `npm test` with real `TEST_DATABASE_URL` | 6 record + 49 contract + 12 Web + 121 API + 16 Worker tests passed | PASS |
| `npm run validate` | All 22 repository architecture/record checks passed | PASS |

## Failures and Corrections

- Contract-first red tests captured the three P1 findings before implementation.
- Ruff/mypy found a Project repository boundary defect during the same review; it was corrected
  before final execution and is covered by Increment 0020.

## Final Status

**Final status:** PASS
