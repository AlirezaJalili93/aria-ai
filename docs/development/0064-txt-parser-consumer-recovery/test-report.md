# Test Report: 0064 — TXT Parser Consumer and Recovery

- **Status:** PASS
- **Increment:** S1-F01/F02 + S1-E04 integration
- **Date:** 2026-09-15
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Python 3.12 repository runtime
- PostgreSQL 16 local Docker service
- Fake deterministic private object reader for CI

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6401 | REQ-6401 | Message and authoritative Job payload validation | Exact v1 IDs accepted; extra/invalid or mismatched state rejected | PASS |
| TC-6402 | REQ-6402 | Concurrent delivery, terminal replay and recovery | One execution; duplicates suppressed; crash redelivery reuses logical rows | PASS |
| TC-6403 | REQ-6403 | Success/failure/final-commit failure | Three state changes atomic; commit failure remains recoverable | PASS |
| TC-6404 | REQ-6404 | Stored TXT read, bytes, UTF-8 and safety failures | Only valid bounded private TXT reaches Parser | PASS |
| TC-6405 | REQ-6405 | Canonical hash vectors | SHA-256 lowercase hex of canonical UTF-8 | PASS |
| TC-6406 | REQ-6406 | Retry and Job-attempt policy | No automatic retry; newly created Parser Job has one execution representation | PASS |
| TC-6407 | REQ-6407 | Queue metric and logs | Queue wait once; correct Version ID; no content/storage/error leakage | PASS |
| TC-6408 | REQ-6408 | PostgreSQL grants/RLS/mutation | Worker can exact read/update, cannot insert/delete or cross-link | PASS |

All test cases above: **PASS**.

## Execution Results

| Gate / command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/txt-parser-runtime-contract.test.js` before implementation | 4/4 failed because approved implementation/evidence files were absent | EXPECTED RED |
| Same TXT Parser contract command after implementation | 4 passed | PASS |
| Focused Worker Consumer/Storage/Guard tests | 21 passed | PASS |
| `TEST_DATABASE_URL=... pytest test_txt_parser_runtime_postgres.py` | 3 passed against PostgreSQL 16 | PASS |
| Alembic `upgrade head` | `0021_txt_parser_worker_access (head)` | PASS |
| Alembic `downgrade 0020_file_upload_allocations` then `upgrade head` | both transitions completed; head restored to `0021` | PASS |
| Focused API Context/Storage regression tests | 61 passed; one upstream deprecation warning | PASS |
| `npm run test:api` | 409 passed, 135 environment-gated skipped; one upstream warning | PASS |
| `npm run test:worker` | 74 passed, 3 environment-gated skipped | PASS |
| `npm run test:ci` | 179 passed | PASS |
| `npm run test:eval` | 35 passed | PASS |
| `npm run test:web` | 35 passed | PASS |
| `npm run lint` | Web ESLint + API/Worker Ruff passed | PASS |
| `npm run typecheck` | Web TypeScript + API 148 files + Worker 34 files passed | PASS |
| `npm run build` | Next.js production build + API/Worker compileall passed | PASS |
| `npm run scan:secrets` | 773 publishable text files inspected; no secret found | PASS |
| `npm run scan:dependencies` | npm, API and Worker scans found no blocking vulnerability | PASS |
| `npm test` | 742 passed across records, 0064 contract, repository contracts, Eval, Web, API and Worker; 138 environment-gated skipped; one upstream warning | PASS |

The 135 API and 3 Worker skips in unconfigured full-suite runs are pre-existing environment-gated
integration cases. The three new 0064 PostgreSQL cases were explicitly rerun with the local real
database configuration and passed.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
