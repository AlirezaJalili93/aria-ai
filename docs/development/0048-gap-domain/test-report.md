# Test Report: 0048 — Gap Domain

- [Development record](./development.md)

## Environment

- Windows 11, Python 3.12, Node.js 24.x, PostgreSQL 16 in Docker
- Disposable database: `aria_gap_test_20260907`; no development database was mutated

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4801 | Domain | Exact Gap type/severity/status vocabularies and default | Only approved values; default `open` |
| TC-4802 | Schema | Logical M006 fields, defaults, constraints and timestamps | Exact J01 table contract |
| TC-4803 | Provenance | Empty, whole-version and bounded Source References | Empty allowed; non-empty refs must be valid same-tenant ready provenance |
| TC-4804 | Security | Cross-tenant Project linkage, FK deletes, RLS/grants | DB-enforced tenant consistency and RESTRICT; no Data API privilege |
| TC-4805 | Lifecycle | `resolved_at` with open/resolved/dismissed | Non-null allowed only for resolved; dismissed remains distinct |
| TC-4806 | Scope | Inspect code/schema/public contracts | No J02/J03 generation, linkage, Clarification, accepted-assumption or API surface |
| TC-4807 | Logging | Persist Gap and inspect structured event | Safe IDs/type/severity/status only; no Source References/Context content |
| TC-4808 | Full gates | Tests, lint, typecheck, build, validate, secrets, diff | Every mandatory gate PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4801, TC-4802, TC-4806, TC-4807 | `node --test scripts/test/gap-domain-contract.test.js` | 4 passed, 0 failed | PASS |
| TC-4801, TC-4803, TC-4805, TC-4807 | focused Domain/Application pytest | 16 passed | PASS |
| TC-4802..TC-4805, TC-4807 | Gap PostgreSQL integration pytest | 11 passed | PASS |
| TC-4801..TC-4807 | full API pytest with PostgreSQL integration | 374 passed, 1 dependency deprecation warning | PASS |
| TC-4808 | `npm run lint` | Web ESLint plus API/Worker Ruff passed | PASS |
| TC-4808 | `npm run typecheck` | Web TypeScript; API 114 and Worker 25 Python source files passed | PASS |
| TC-4808 | `npm run build` | Next.js production build and API/Worker compileall passed | PASS |
| TC-4808 | `npm test` | All repository test stages passed | PASS |
| TC-4808 | `npm run validate` | Architecture and development-record validation passed | PASS |
| TC-4808 | `npm run scan:secrets` and `git diff --check` | No secret finding or whitespace error | PASS |

## Commands and Results

```text
node --test scripts/test/gap-domain-contract.test.js
  4 passed, 0 failed

node scripts/run-uv.mjs --project apps/api run pytest -q \
  apps/api/tests/test_gap_domain.py apps/api/tests/test_gap_application.py
  16 passed

$env:TEST_DATABASE_URL='postgresql+asyncpg://***@127.0.0.1:5432/aria_gap_test_20260907'
node scripts/run-uv.mjs --project apps/api run pytest -q \
  apps/api/tests/test_gap_postgres.py
  11 passed

node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests
  374 passed, 1 warning

npm run lint
  PASS
npm run typecheck
  PASS
npm run build
  PASS
npm test
  PASS
npm run validate
  PASS
npm run scan:secrets
  PASS
git diff --check
  PASS
```

The warning is an upstream Starlette deprecation notice about `httpx`; it is unrelated to J01 and
does not affect test behavior.

## Final Status

**Final status:** PASS
