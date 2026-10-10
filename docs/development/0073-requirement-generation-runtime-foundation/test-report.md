# Test Report: 0073 — Requirement Generation Runtime Foundation

- [Development record](./development.md)

## Environment

- Windows 11, Python 3.12, Node.js 24.x, npm 11.x
- Docker Desktop PostgreSQL 16 (`aria_0073_test_20260922`, isolated test database)
- Migration head `0027_requirement_gen_runtime`
- Fake deterministic AI-02 Provider and synthetic fixtures only

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-7301 | Contract/Application | Internal scheduling and exact Context revision binding | One atomic Job/Outbox pair contains the frozen snapshot pointer |
| TC-7302 | Contract | Queue/Outbox envelope | Only the three approved identifiers cross the transport boundary |
| TC-7303 | Queue | Outbox publisher routing | AI-02 event maps only to `aria.requirements.generate.v1` with retry disabled |
| TC-7304 | Worker | Synthetic AI-02 execution | Exact snapshot produces validated draft Requirements without paid calls |
| TC-7305 | PostgreSQL | Atomic success | Requirement/conflict writes and Job success commit together |
| TC-7306 | Recovery | Duplicate and forced commit failure | No duplicate Requirements; same Job remains recoverable |
| TC-7307 | Privacy/Safety | Logging, payload and composition leakage checks | No Context/customer text; no hosted task or real provider activation |
| TC-7308 | Architecture | No route/chaining/hosted activation | Deferred capabilities remain absent |
| TC-7309 | Quality | Full repository gates | Tests, lint, typecheck, build, validate and secret scan PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-7301 | API scheduler unit + PostgreSQL suite | Exact revision persisted; one Job/Outbox; second active command rejected | PASS |
| TC-7302 | Runtime contract + consumer message tests | Exact three-field Queue envelope; customer/tenant payload rejected | PASS |
| TC-7303 | Outbox publisher + controlled Celery task tests | Event mapped to canonical task; `retry=false`; `autoretry_for=()` | PASS |
| TC-7304 | Synthetic adapter + Worker PostgreSQL suite | Exact Context snapshot produced one validated draft Requirement | PASS |
| TC-7305 | Worker PostgreSQL atomic-success test | Requirement and Job success committed together | PASS |
| TC-7306 | Duplicate and forced-commit recovery tests | Duplicate suppressed; rollback left zero rows and same recoverable Job | PASS |
| TC-7307 | Contract/privacy/composition tests | Synthetic only; no hosted registration or sensitive envelope/log fields | PASS |
| TC-7308 | Architecture scan and code review | No public route, AI-01 chaining or real Provider activation | PASS |
| TC-7309 | Full quality gates | Tests, lint, strict typecheck, build, validation and secret scan passed | PASS |

## Commands and Results

```text
npm run test:requirement-generation-runtime
  PASS — 4 passed

focused API pytest
  PASS — 30 passed
focused Worker pytest
  PASS — 14 passed

TEST_DATABASE_URL=... pytest -q
  apps/api/tests/test_requirement_generation_postgres.py
  apps/api/tests/test_requirement_generation_jobs_postgres.py
  apps/worker/tests/test_requirement_generation_runtime_postgres.py
  PASS — 10 passed

alembic upgrade head
alembic downgrade 0026_context_structuring_runtime
alembic upgrade head
  PASS — head 0027_requirement_gen_runtime; downgrade/re-upgrade passed

npm run test:api
  PASS — 444 passed, 150 skipped
npm run test:worker
  PASS — 144 passed, 14 skipped
npm run test:ci
  PASS — 185 passed
npm run test:eval
  PASS — 35 passed
npm run test:web
  PASS — 40 passed

npm run lint:api && npm run lint:worker
  PASS
npm run typecheck:api && npm run typecheck:worker
  PASS — API 158 and Worker 57 source files
npm run build
  PASS — Web production build and API/Worker byte compilation
npm test
  PASS
npm run validate
  PASS
npm run scan:secrets
  PASS — 883 publishable text files inspected
git diff --check
  PASS
```

## Final Status

**Final status:** PASS
