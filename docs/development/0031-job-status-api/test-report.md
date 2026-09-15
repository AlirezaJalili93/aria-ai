# Test Report: 0031 Job Status API

[Development record](./development.md)

## Environment

- Windows 11 host, repository worktree `staging-migrations`
- Python 3.12 API environment managed by `uv`
- Node.js/npm repository toolchain
- API tests use authenticated fakes; repository contract asserts Account-scoped SQL filtering.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3101 | API contract | Read a failed Job | Exact envelope and only approved fields are returned; safe error object is mapped |
| TC-3102 | Contract/unit | Canonical vocabulary and status fields | `job_type` and approved status/progress/retryability fields are used |
| TC-3103 | Security/API | Missing or cross-tenant Job | Both return `404 RESOURCE_NOT_FOUND` without existence disclosure |
| TC-3104 | Security/contract | Inspect public response surface | Payload, operational identifiers, traceback and secret fields are absent |
| TC-3105 | Architecture | Inspect deferred boundaries | No migration, retry policy, progress taxonomy, SSE or frontend polling behavior is invented |
| TC-3106 | API regression | Run all API tests | Existing auth, tenant, context, project and Job persistence behavior remains green |
| TC-3107 | Quality | Run lint, typecheck, build and validation | All repository quality gates pass |

## Execution Results

| ID | Command | Actual | Status |
|---|---|---|---|
| TC-3101–TC-3103 | `node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests/test_job_status_api.py` | 3 tests passed | PASS |
| TC-3104–TC-3105 | `node --test scripts/test/job-status-contract.test.js` | 2 contract tests passed | PASS |
| TC-3106 | `node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests/test_schedule_job_application.py apps/api/tests/test_job_status_api.py` | 5 tests passed | PASS |
| TC-3107 (focused) | `node scripts/run-uv.mjs --project apps/api run ruff check apps/api/app apps/api/tests`; `node scripts/run-uv.mjs --project apps/api run mypy apps/api/app packages/observability/src scripts/db` | Ruff passed; mypy reported no issues in 81 source files | PASS |
| TC-3106 (repository) | `npm test` | Records 6, contracts 86, Web 18, API 149 passed/33 skipped, Worker 26 passed | PASS |
| TC-3107 (repository) | `npm run lint`; `npm run typecheck`; `npm run build`; `npm run validate` | Web/API/Worker lint, strict type checks and builds passed; architecture validation passed 22/22 | PASS |

## Notes

- The focused pytest run emitted only the existing Starlette/httpx deprecation and Windows pytest
  cache-permission warnings.
- Full repository gates passed. The only output warnings were the existing Starlette/httpx
  deprecation and Windows pytest cache-permission warnings.

## Final Status

**Final status:** PASS
