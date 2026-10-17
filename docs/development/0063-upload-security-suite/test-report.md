# Test Report: 0063 — Upload Security Suite

- **Status:** PASS
- **Increment:** S1-L04
- **Date:** 2026-09-15
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js repository runtime
- Python 3.12 repository runtime
- PostgreSQL 16 local Docker service
- Railway Staging API at commit `a67bfe461d8ffc057b4632ee242f48b267045b1b`
- Supabase Staging project `aria-ai-staging` (`ACTIVE_HEALTHY`) and private bucket
  `aria-staging-project-content`

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6301 | REQ-6301 | MIME spoof, invalid UTF-8, binary executable and executable-looking text | Invalid binary/non-text rejected; inert valid text accepted but never executed | PASS |
| TC-6302 | REQ-6302 | Exact and oversized byte/character payloads | Boundaries accepted; oversize rejected before storage | PASS |
| TC-6303 | REQ-6303 | Traversal, separator, control, dot, long and encoded filenames | Unsafe basename rejected; display name never controls object path | PASS |
| TC-6304 | REQ-6304 | Adapter and hosted bucket anonymous-access checks | No public/upsert surface; bucket private; anonymous public read, private download and list denied; sentinel removed | PASS |
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
| `npm run test:api` with PostgreSQL | 543 passed; opt-in hosted test skipped in local run | PASS |
| `npm run test:worker` | 58 passed | PASS |
| `npm run build` | Next.js production build and API/Worker compile checks passed | PASS |
| `npm run scan:secrets` | 758 publishable text files; no finding | PASS |
| `git diff --check` | No whitespace error | PASS |
| Railway `/health/live` and `/health/ready` | HTTP 200; exact release SHA `a67bfe461d8ffc057b4632ee242f48b267045b1b`; configuration/database/queue passed | PASS |
| Hosted private-bucket sentinel `d2ef32a8-9ca6-495b-8630-dacba89c30c8` | Upload PASS; anonymous public read/private download/list each denied with HTTP 400; delete PASS; no secret or customer data exposed | PASS |
| Final `npm test` | Records 6, CI 179, Eval 35, Web 35, API 409 passed/135 environment-dependent skipped, Worker 58; command exited 0 | PASS |
| Final `npm run validate` | 23 architecture and development-record checks passed | PASS |

Hosted evidence ran in the active Railway API container using runtime-injected credentials. The
probe generated a random non-customer sentinel and a server-only object key, uploaded it to the
private Staging bucket, and performed three requests without credentials. Public-object GET,
private-object GET and bucket-list POST each returned HTTP 400. Mandatory cleanup succeeded. The
probe emitted only its synthetic test identifier, bounded statuses and HTTP codes; it did not emit
the object key, object URL, signed URL, content or credential values.

The first build attempt hit the environment's inaccessible default uv cache after the Web build.
The complete build was rerun with the workspace-local uv cache and passed. This is recorded as an
environment retry, not a code failure.

The Python vulnerability audit remains `INCOMPLETE / ENVIRONMENTAL FAILURE`, not PASS, because the
auditor could not be retrieved from PyPI due TLS availability failure documented in increment 0062.

The final `npm test` and `npm run validate` gates were rerun after sealing this report and both
completed successfully. Pytest emitted only environment cache warnings caused by the restricted
local `.pytest_cache` path; they did not change test outcomes.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
