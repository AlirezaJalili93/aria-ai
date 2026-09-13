# Test Report: 0061 — Cross-Tenant Security Suite

- **Status:** PASS
- **Increment:** S1-L03
- **Date:** 2026-09-13
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js repository runtime
- Python 3.12 repository runtime
- PostgreSQL 16 local Docker service

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6101 | REQ-6101 | Seed Tenant A and Tenant B together | Independent identities, Accounts, Memberships, Projects and child resources coexist | PASS |
| TC-6102 | REQ-6102 | Missing, empty, malformed and foreign Account selector | 400/400/400/403 stable contracts; foreign Account ID absent from log | PASS |
| TC-6103 | REQ-6103 | Tenant A GET/PATCH/DELETE Tenant B Project | Same 404 envelope as a missing Project; no mutation | PASS |
| TC-6104 | REQ-6104 | Guess Context, Requirement and Gap identifiers | Same safe 404 as missing resources; no mutation/content leak | PASS |
| TC-6105 | REQ-6105 | Guess Scope and Job selectors | Public Scope selector stays project/version based; safe 404; no mutation | PASS |
| TC-6106 | REQ-6106 | Query Tenant B internal UUIDs through repositories/Data API role | Repositories return none; private tables use RLS/no grants; exact Scope UUID denied | PASS |
| TC-6107 | REQ-6107 | Inspect denial audit events | Bounded identifiers only; no secondary probe, child UUID or customer content | PASS |
| TC-6108 | REQ-6108 | Contract and full quality gates | CI includes suite; no security/debug endpoint; repository remains green | PASS |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/cross-tenant-security-contract.test.js` | 3 passed | PASS |
| `npm run lint:api` | Passed | PASS |
| `npm run typecheck:api` | Passed, 143 source files | PASS |
| `pytest -q apps/api/tests/test_cross_tenant_security.py` with PostgreSQL | 3 passed; HTTP, Repository and RLS/Data API evidence | PASS |
| Focused affected API regression suite | 34 passed | PASS |
| `npm run lint` | Web ESLint plus API/Worker Ruff passed | PASS |
| `npm run typecheck` | Web TypeScript, API mypy (143 files) and Worker mypy (28 files) passed | PASS |
| `npm test` | Records 6, contracts 173, eval 35, web 35, API 503 and Worker 58 passed | PASS |
| `npm run build` | Next.js production build and API/Worker compile checks passed | PASS |
| `npm run validate` | 23 architecture and development-record checks passed | PASS |
| `npm run scan:secrets` | 739 publishable text files inspected; no finding | PASS |
| `git diff --check` | No whitespace error | PASS |

The first PostgreSQL attempt could not connect because Docker Desktop was stopped. After restoring
the documented local PostgreSQL 16 service, the complete database-backed suite and every final gate
above passed. The remaining Pytest output consists only of the existing Starlette `httpx2`
deprecation notice and Windows cache-directory permission warnings; neither affects execution or
test results.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
