# Test Report: 0065 — Context Source Management and Explicit Retry

- **Status:** PASS
- **Increment:** S1-D04 backend prerequisites + S1-E05 explicit Parser recovery
- **Date:** 2026-09-19
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js repository runtime
- Python 3.12 API and Worker runtimes
- PostgreSQL 16 local Docker service
- Database connection supplied through local environment variables; no credential stored in this report

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6501 | REQ-6501 | List pagination, ordering and deleted filtering | Stable opaque cursor; latest-first; deleted rows absent | PASS |
| TC-6502 | REQ-6502 | Source detail projection | Approved Source/Version/Job summaries only; no content/Storage fields | PASS |
| TC-6503 | REQ-6503 | Owner/Admin/Member, cross-Tenant and missing archive | Approved actor succeeds; every non-visible case is safe 404 | PASS |
| TC-6504 | REQ-6504 | Archive with Version/Storage/downstream history | Source becomes deleted; Version and Storage reference remain unchanged | PASS |
| TC-6505 | REQ-6505 | Failed recoverable Parser Job retry | New queued child; immediate-parent link; same SourceVersion; immutable parent | PASS |
| TC-6506 | REQ-6506 | Same-key replay, different-key concurrency and active Job | Replay is stable; conflict/duplicate execution is rejected atomically | PASS |
| TC-6507 | REQ-6507 | Retryability and error mapping | Only approved Parser Storage failure is retryable; stable 404/409 contracts | PASS |
| TC-6508 | REQ-6508 | Tenant scope, database constraints and log leakage | Cross-Tenant blocked; constraints enforced; sensitive fields absent | PASS |

All test cases above: **PASS**.

## Execution Results

| Gate / command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/context-source-management-contract.test.js` before implementation | 4 expected failures because 0065 evidence and implementation were absent | EXPECTED RED |
| `npm run test:context-source-management` | 4 passed | PASS |
| Focused Source management, retry, API and PostgreSQL tests | 21 passed | PASS |
| Alembic upgrade `0021 -> 0022` | `0022_context_source_management (head)` reached | PASS |
| Alembic downgrade `0022 -> 0021` | downgrade completed without restoring unsafe authority | PASS |
| Alembic re-upgrade `0021 -> 0022` | head restored | PASS |
| `npm run test:ci` | 179 passed | PASS |
| `npm test` | 894 passed, 1 environment-gated skipped; one upstream warning | PASS |
| `npm run lint` | Web ESLint and API/Worker Ruff passed | PASS |
| `npm run typecheck` | Web TypeScript and API/Worker mypy passed | PASS |
| `npm run build` | Web production build and API/Worker compile checks passed | PASS |
| `npm run validate` | Architecture, dependency-boundary and development-record validation passed | PASS |
| `npm run scan:secrets` | No secret found in publishable repository files | PASS |
| `npm run scan:dependencies` | No blocking npm/API/Worker vulnerability found | PASS |

The single API skip is an existing environment-gated case outside 0065. The API test suite emits
one upstream Starlette/httpx deprecation warning; no 0065 test is skipped or downgraded.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
