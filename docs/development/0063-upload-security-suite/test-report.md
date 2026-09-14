# Test Report: 0063 — Upload Security Suite

- **Status:** PENDING
- **Increment:** S1-L04
- **Date:** 2026-09-14
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js repository runtime
- Python 3.12 repository runtime
- PostgreSQL 16 local Docker service
- Supabase Staging project `aria-ai-staging` (`COMING_UP` after owner restore; hosted gate pending)

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6301 | REQ-6301 | MIME spoof, invalid UTF-8, binary executable and executable-looking text | Invalid binary/non-text rejected; inert valid text accepted but never executed | PASS |
| TC-6302 | REQ-6302 | Exact and oversized byte/character payloads | Boundaries accepted; oversize rejected before storage | PASS |
| TC-6303 | REQ-6303 | Traversal, separator, control, dot, long and encoded filenames | Unsafe basename rejected; display name never controls object path | PASS |
| TC-6304 | REQ-6304 | Adapter and hosted bucket public-access checks | No public/upsert surface; bucket private; anonymous object GET denied | PARTIAL — hosted evidence pending |
| TC-6305 | REQ-6305 | Tenant A uploads against Tenant B Project | Safe 404/no object upload/no state | PASS |
| TC-6306 | REQ-6306 | Same/different payload with repeated Idempotency-Key | Exact replay/no duplicate; conflict before second upload | PASS |
| TC-6307 | REQ-6307 | DB commit and compensation failure injection | Delete attempted; failure observable; no false success | PASS |
| TC-6308 | REQ-6308 | Feature flag and log/response leakage corpus | Disabled by default; no filename/content/object URL/secret leak | PASS |
| TC-6309 | REQ-6309 | Concurrent claim, unknown Put outcome, retry and compensation | One uploader; stable IDs/key; recovery blocks blind re-upload; compensated retry reuses allocation | PASS |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/upload-security-contract.test.js` | 5 passed | PASS |
| Focused allocation/Application/Supabase adapter/PostgreSQL suite | 18 passed | PASS |
| `pytest -q apps/api/tests/test_file_context_postgres.py` with PostgreSQL | 5 passed: atomic claim, stable recovery allocation, Tenant A/B and RLS | PASS |
| Alembic `downgrade 0019_operational_dashboard_views`, `upgrade head`, `current` | Round trip passed; head=`0020_file_upload_allocations` | PASS |
| `npm run lint` | Web ESLint plus API/Worker Ruff passed | PASS |
| `npm run typecheck` | Web TypeScript, API mypy 148 files, Worker mypy 28 files | PASS |
| `npm run test:ci` | 179 passed | PASS |
| `npm run test:eval` | 35 passed | PASS |
| `npm run test:web` | 35 passed | PASS |
| `npm run test:api` with PostgreSQL | 543 passed; hosted sentinel test skipped | PASS / hosted pending |
| `npm run test:worker` | 58 passed | PASS |
| `npm run build` | Next.js production build and API/Worker compile checks passed | PASS |
| `npm run scan:secrets` | 758 publishable text files; no finding | PASS |
| `git diff --check` | No whitespace error | PASS |
| `npm run validate` | All architecture checks passed; validator correctly rejected this record's non-PASS final status while hosted evidence is pending | BLOCKED AS DESIGNED |

Hosted evidence attempt: the owner restored Supabase project `aria-ai-staging`; it subsequently
reported `ACTIVE_HEALTHY`. A read-only query confirmed bucket `aria-staging-project-content` exists
with `public=false`, and that it currently contains no object suitable for an anonymous-access
probe. The sentinel upload/anonymous GET test was not enabled because server Storage credentials
are not injected into this runtime. Bucket configuration is partial evidence only; anonymous denial
is not claimed as PASS.

The first build attempt hit the environment's inaccessible default uv cache after the Web build.
The complete build was rerun with the workspace-local uv cache and passed. This is recorded as an
environment retry, not a code failure.

The Python vulnerability audit remains `INCOMPLETE / ENVIRONMENTAL FAILURE`, not PASS, because the
auditor could not be retrieved from PyPI due TLS availability failure documented in increment 0062.

`npm test` is not reported as a completed final gate: its mandatory development-record phase cannot
pass until TC-6304 hosted evidence is complete. All constituent functional suites were run
separately and passed as recorded above.

## Final Status

**Final status:** PENDING

**Unapproved assumptions:** None
