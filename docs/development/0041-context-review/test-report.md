# Test Report: 0041 — Structured Context Review

- [Development record](./development.md)

## Environment

- Windows 11, Node.js 24.x, npm 11.x
- Python 3.12, uv-managed API/Worker environments
- Docker Desktop local PostgreSQL 16 and Redis 7
- `TEST_DATABASE_URL=postgresql+asyncpg://aria_local:aria_local_dev@127.0.0.1:5432/aria_local`
- Migration head includes `0010_context_item_review`

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4101 | Contract | OpenAPI, migration, UI and deferred-scope contract checks | Approved H04 contract is present; unapproved actions absent |
| TC-4102 | Application | Current-version list, source filter, edit, stale CAS and immutable state | Tenant scope, provenance preservation, distinct application errors |
| TC-4103 | PostgreSQL | Trigger, current-version filter, provenance filter and atomic review CAS | Database owns timestamps and stale/non-proposed mutations are rejected |
| TC-4104 | API | JWT/tenant authorization, envelopes, pagination, safe 404 and two 409 mappings | Stable response/error contracts |
| TC-4105 | Web | RTL tabs, provenance disclosure, review actions and recovery states | Accessible canonical six-tab UI with tokenized styles |
| TC-4106 | Full gates | Repository tests, lint, typecheck, build and validation | All quality gates PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4101 | `node scripts/test/context-review-contract.test.js` | 4 passed | PASS |
| TC-4102 | `pytest -q apps/api/tests/test_context_review_application.py apps/api/tests/test_context_items_api.py` | 6 passed | PASS |
| TC-4103 | `TEST_DATABASE_URL=... pytest -q apps/api/tests/test_context_item_postgres.py` | 18 passed | PASS |
| TC-4104 | Included in `npm run test:api` | 265 API tests passed | PASS |
| TC-4105 | `npm test --workspace @aria/web` and `npm run build:web` | 19 Web tests passed; production build passed | PASS |
| TC-4106 | `npm run test:ci`, `npm run lint`, `npm run typecheck`, `npm run build`, `npm test`, `npm run validate` | Final repository gates passed | PASS |

## Commands and Results

```text
npm run test:ci       PASS — 112 passed
npm run test:api      PASS — 265 passed (2 environment cache warnings only)
npm run test:worker   PASS — 55 passed (1 environment cache warning only)
npm test --workspace @aria/web
                      PASS — 19 passed
npm run build:web     PASS — Next.js production build completed
npm run build         PASS — Web, API and Worker build completed
npm run lint          PASS — Web, API and Worker checks passed
npm run typecheck     PASS — Web, API and Worker strict checks passed
npm test              PASS — all repository test groups passed
npm run validate      PASS — architecture and development-record validation passed
```

## Final Status

**Final status:** PASS
