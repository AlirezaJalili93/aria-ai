# Test Report: 0045 — Requirement CRUD and Human Review

- [Development record](./development.md)

## Environment

- Windows 11, Node.js 24.x, npm 11.x
- Python 3.12, uv-managed API/Worker environments
- Docker Desktop disposable PostgreSQL 16 container on loopback port 55432
- Migration head includes `0013_requirement_crud`
- The shared local PostgreSQL database was not used for migration downgrade/destructive tests.

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4501 | API/Repository | List, category/status filters, hidden terminal states and keyset cursor | Approved rows only; stable descending page; public fields only |
| TC-4502 | Application/API | Manual create with/without current Context Version | Server binds approved fields; missing Context returns stable 422 |
| TC-4503 | Idempotency | Same key/same input and same key/different input | Same resource replay or 409 conflict; no duplicate write |
| TC-4504 | Concurrency | PATCH, explicit-null note, confirmation and stale timestamp | Atomic update/demotion or distinct 409 version/state error |
| TC-4505 | Lifecycle | DELETE draft and attempt terminal/non-draft mutation | Soft removed only; no physical delete; invalid state rejected |
| TC-4506 | Security | Missing, deleted and cross-tenant Project/Requirement | Uniform safe 404 and tenant-scoped persistence predicates |
| TC-4507 | Privacy | Requirement events and public response | No title, description, acceptance note, raw provenance or internal IDs in logs/API |
| TC-4508 | PostgreSQL | Migration upgrade/downgrade, index, list/mutation/idempotency behavior | Schema and repository behavior match ADR-032 |
| TC-4509 | Full gates | Repository tests, lint, typecheck, build, validate and secret scan | Every mandatory gate PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4501 | focused API/Application and PostgreSQL suites | 59 Requirement regression tests and 23 PostgreSQL tests passed | PASS |
| TC-4502 | focused Application/API suites | Context binding and 422 cases passed | PASS |
| TC-4503 | focused Application/PostgreSQL suites | Replay/conflict/no-duplicate cases passed | PASS |
| TC-4504 | focused Application/API/PostgreSQL suites | CAS, explicit null, demotion and conflict cases passed | PASS |
| TC-4505 | focused Application/API/PostgreSQL suites | Draft soft-removal and terminal-state rejection passed | PASS |
| TC-4506 | focused API/PostgreSQL suites | Safe-not-found and tenant predicates passed | PASS |
| TC-4507 | structured-event/API tests | Approved fields only; sensitive content absent | PASS |
| TC-4508 | isolated PostgreSQL 16 suites | 23 passed | PASS |
| TC-4509 | complete quality gates | Tests, lint, typecheck, build, validation and secret scan passed | PASS |

## Commands and Results

```text
node --test scripts/test/requirement-crud-contract.test.js
                      PASS — 3 passed
focused Requirement API/Application/regression suites
                      PASS — 59 passed
isolated TEST_DATABASE_URL pytest requirement PostgreSQL suites
                      PASS — 23 passed
npm run typecheck:api
                      PASS — 105 source files
test:ci             PASS — 122 passed
test:eval           PASS — 8 passed
test:web            PASS — 19 passed
test:api            PASS — 347 passed with isolated PostgreSQL integration enabled
test:worker         PASS — 57 passed
npm run lint        PASS
npm run typecheck   PASS — API 105 and Worker 25 Python source files; Web strict TypeScript
npm run build       PASS — Web production build plus API/Worker byte compilation
npm test            PASS
npm run validate    PASS
npm run scan:secrets
                      PASS — 532 publishable text files inspected
git diff --check    PASS — no whitespace errors; Windows line-ending notices only
```

## Final Status

**Final status:** PASS
