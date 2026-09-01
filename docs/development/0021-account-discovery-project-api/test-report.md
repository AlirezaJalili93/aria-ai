# Test Report: 0021 Account Discovery and Project API

- Increment ID: `0021-account-discovery-project-api`
- Date: 2026-09-01
- [Development record](./development.md)

## Environment

Windows workspace; Node.js 24+; Python 3.12; FastAPI/SQLAlchemy; PostgreSQL integration database
when `TEST_DATABASE_URL` is configured. Secrets are not recorded.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2101 | API/Contract | Discover Accounts with valid JWT | Only active memberships returned as exact `id/role` items in collection envelope |
| TC-2102 | Security | Discover Accounts without JWT or with inactive memberships | Authentication enforced; invited/suspended omitted; no identity/profile metadata exposed |
| TC-2103 | API/Domain | Create Project with documented body | Trimmed title, exact type and initial Project representation returned |
| TC-2104 | Negative | Whitespace/overlong title or undocumented field | Stable validation rejection; no write |
| TC-2105 | Integration | Retry same key and same payload | Same Project returned; no duplicate row |
| TC-2106 | Integration | Retry same key with different payload | `409 IDEMPOTENCY_CONFLICT` |
| TC-2107 | Repository/API | List more than one page | Descending `(created_at,id)` order and opaque continuation without gaps/duplicates |
| TC-2108 | Contract | Omit, exceed or corrupt list controls | Default 20, max 100, invalid values rejected |
| TC-2109 | Security | Access missing or cross-tenant Project | Same `404 RESOURCE_NOT_FOUND` response |
| TC-2110 | Security | Mutating route without active selected Membership | Existing 400/403 tenant contract preserved |
| TC-2111 | API/Integration | PATCH title with matching timestamp | Update succeeds and returns advanced `updated_at` |
| TC-2112 | Concurrency | PATCH stale timestamp | `409 VERSION_CONFLICT`; persisted Project unchanged |
| TC-2113 | Authorization | Owner/admin/member delete | Owner/admin get 204; member denied |
| TC-2114 | Soft delete | Read/list/update deleted Project | Ordinary API returns safe 404 and does not mutate it |
| TC-2115 | Privacy/Logging | Mutations and denied access | Approved events/IDs emitted; title/JWT/raw payload absent |
| TC-2116 | Contract/Gate | OpenAPI, architecture, full repository gates | Canonical paths/schemas present and all mandatory gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2101, TC-2102 | API tests in `test_project_api.py` and PostgreSQL discovery test | Exact envelope/fields; unauthorized rejected; invited/suspended excluded | PASS |
| TC-2103, TC-2104 | Project Domain/Application/API tests | Trimmed valid title accepted; empty/overlong/extra field rejected | PASS |
| TC-2105, TC-2106 | Real PostgreSQL concurrent create plus Application replay/conflict tests | Two concurrent same-key requests returned one exact Project; changed payload returned conflict | PASS |
| TC-2107, TC-2108 | Repository PostgreSQL keyset test and HTTP list tests | DESC ordering, opaque cursor, default 20/max 100 and validation passed | PASS |
| TC-2109, TC-2110 | HTTP safe-404 and existing Tenant dependency regressions | Missing/cross-tenant response indistinguishable; active Membership enforced | PASS |
| TC-2111, TC-2112 | Application/API optimistic concurrency tests | Matching timestamp advanced update; stale timestamp produced `VERSION_CONFLICT` without mutation | PASS |
| TC-2113, TC-2114 | Application/API/PostgreSQL soft-delete tests | Owner/admin path returns 204; member denied; deleted Project excluded | PASS |
| TC-2115 | Structured log assertions and secret scan | Required IDs/events present; Title/JWT/key/raw payload absent | PASS |
| TC-2116 | `npm run lint` | Web ESLint, API/Worker Ruff passed | PASS |
| TC-2116 | `npm run typecheck` | Web TypeScript and strict API/Worker mypy passed | PASS |
| TC-2116 | `npm run test:ci` | 53 contract/security/config tests passed | PASS |
| TC-2116 | `npm run test:web` | 12 tests passed | PASS |
| TC-2116 | `npm run test:worker` | 16 tests passed | PASS |
| TC-2101–TC-2115 | PostgreSQL 18 temporary isolated cluster; `pytest ... test_account_bootstrap_postgres.py test_project_postgres.py` | 19 migration/integration tests passed | PASS |
| TC-2116 | `npm run build` | Next.js production build plus API/Worker compile passed | PASS |
| TC-2115, TC-2116 | `npm run scan:dependencies` | npm/pip audits found no known vulnerabilities | PASS |
| TC-2115, TC-2116 | `npm run scan:secrets` | 248 publishable text files inspected; no secret found | PASS |
| TC-2101–TC-2116 | `npm test` | Full repository test command passed | PASS |
| TC-2101–TC-2116 | `npm run validate` | Architecture and development-record gates passed | PASS |
| TC-2101–TC-2116 | [GitHub PR #15 checks](https://github.com/AlirezaJalili93/aria-ai/pull/15/checks) | Quality 1m26s, Security baseline 27s, Vercel and Preview Comments passed | PASS |

## Failures and Corrections

- Contract-first checks initially failed because the new routes and migration did not yet exist;
  implementation closed them.
- Senior review found actor-scoped idempotency uniqueness. It was corrected to Account-scoped
  uniqueness and covered by cross-actor replay plus concurrent PostgreSQL tests.
- The first local dependency scan attempt could not acquire the sandboxed uv tool lock. Re-running
  the unchanged audit with approved tool-cache access passed for npm, API and Worker dependencies.
- Local observability package reinstall was blocked by a Windows temporary executable lock. Pytest
  now explicitly loads the workspace source path, which also prevents stale installed workspace
  copies from masking source changes.
- The first final architecture validation scanned the task-local `.uv-cache` and reported two broken
  links inside downloaded third-party package metadata. The exact generated cache was removed;
  re-running the unchanged validator passed all 22 repository checks.

## Final Status

**Final status:** PASS
