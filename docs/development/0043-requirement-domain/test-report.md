# Test Report: 0043 — Requirement Domain

- [Development record](./development.md)

## Environment

- Windows 11, Node.js 24.x, npm 11.x
- Python 3.12, uv-managed API/Worker environments
- Docker Desktop local PostgreSQL 16 and Redis 7
- `TEST_DATABASE_URL=postgresql+asyncpg://aria_local:aria_local_dev@127.0.0.1:5432/aria_local`
- Migration head includes `0011_requirements`

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4301 | Domain | Exact enums, mandatory priority, creator rule, confidence and timestamp invariants | Only canonical values construct valid entities |
| TC-4302 | Application | Existing/future Context Version, provenance resolution, offset validation and safe event | Persist only valid same-tenant Requirement without content logging |
| TC-4303 | PostgreSQL | Columns, defaults, checks, indexes, trigger and restrictive FKs | M005 matches the approved contract |
| TC-4304 | Security | Composite tenant FK, RLS and Data API grants | Cross-tenant row fails and public roles remain deny-by-default |
| TC-4305 | Integration | Real repository persistence with ready Source Version and future/cross-tenant rejection | Application and PostgreSQL boundaries agree |
| TC-4306 | Contract/scope | ADR, migration, module dependency and deferred-surface checks | No API, generation, merge, dedupe or acceptance note introduced |
| TC-4307 | Recovery | Downgrade to 0010 and re-upgrade to head | Requirement schema removes and recreates safely |
| TC-4308 | Full gates | Repository tests, lint, typecheck, build and validation | All mandatory gates PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4301 | focused Domain/Application suite | 19 passed | PASS |
| TC-4302 | focused Application and logging cases | Included in 19 focused tests | PASS |
| TC-4303 | PostgreSQL suite | 15 passed | PASS |
| TC-4304 | PostgreSQL security cases | RLS/grants/composite FK checks passed | PASS |
| TC-4305 | repository integration cases | Ready provenance persisted; future/cross-tenant rejected | PASS |
| TC-4306 | Requirement contract suite | 4 passed; full contract CI 116 passed | PASS |
| TC-4307 | migration recovery case | Downgrade to 0010 and re-upgrade to head passed | PASS |
| TC-4308 | full quality gates | Tests, lint, typecheck, build and validation passed | PASS |

## Commands and Results

```text
node --test scripts/test/requirement-domain-contract.test.js
                      PASS — 4 passed
pytest -q test_requirement_domain.py test_requirement_application.py
                      PASS — 19 passed
TEST_DATABASE_URL=... pytest -q test_requirement_postgres.py
                      PASS — 15 passed
npm run test:ci       PASS — 116 passed
npm run test:api      PASS — 299 passed; one dependency deprecation warning
npm run test:eval     PASS — 8 passed
npm run test:web      PASS — 19 passed
npm run test:worker   PASS — 55 passed
npm run lint          PASS
npm run typecheck     PASS
npm run build         PASS
npm test              PASS
npm run validate      PASS
npm run scan:secrets  PASS — 511 publishable text files inspected
alembic check         KNOWN PRE-EXISTING — only G05 usage-record metadata ownership reported;
                      no Requirement schema operation detected
```

## Final Status

**Final status:** PASS
