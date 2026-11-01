# Test Report: 0044 — Requirement Generation

- [Development record](./development.md)

## Environment

- Windows 11, Node.js 24.x, npm 11.x
- Python 3.12, uv-managed API/Worker environments
- Docker Desktop local PostgreSQL 16 and Redis 7
- `TEST_DATABASE_URL=postgresql+asyncpg://aria_local:aria_local_dev@127.0.0.1:5432/aria_local`
- Migration head includes `0012_requirement_generation`

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4401 | Application | Exact Context set unchanged/inserted/updated/predicate-exited | Only an identical revision vector can reach persistence |
| TC-4402 | Validation | Candidate schema, unsupported flag, provenance and empty batch | Valid batch passes; deterministic defects repair/fail safely |
| TC-4403 | Merge | Duplicate group, confidence difference, existing active/removed Requirements | Stable refs only; no human decision overwrite/reactivation |
| TC-4404 | Atomicity | Conflict Requirements and Outbox success/failure | Both commit together or all business writes roll back |
| TC-4405 | Replay | Same-tenant succeeded/failed generation Job, including zero generated rows | Current generated batch or safe terminal result returned without AI, Usage or new writes |
| TC-4406 | Repair/Metering | Repairable/non-repairable defects and max 0/1 | Same boundary repairs once; each returned invocation has Usage |
| TC-4407 | Worker/architecture | Worker invokes shared Application use case | No duplicate rule or provider SDK in Worker/Application |
| TC-4408 | PostgreSQL | Migration, exact snapshot, tenant scope, replay and rollback | Database behavior matches ADR-031 |
| TC-4409 | Privacy | Structured events and Outbox payload | Approved identifiers/counts only; no content/provenance |
| TC-4410 | Full gates | Repository test/lint/typecheck/build/validate/secret scan | All mandatory gates PASS |

## Execution Results

| ID | Command | Actual | Status |
| --- | --- | --- | --- |
| TC-4401 | focused Application suite | 28 passed with exact-set and terminal replay variants | PASS |
| TC-4402 | focused Application suite | Candidate/provenance/empty tests passed | PASS |
| TC-4403 | focused Application suite | Exact merge and active/removed policies passed | PASS |
| TC-4404 | Application + PostgreSQL rollback cases | Passed | PASS |
| TC-4405 | Application + PostgreSQL replay cases | Passed | PASS |
| TC-4406 | repair and Usage cases | Passed | PASS |
| TC-4407 | Worker wrapper + contract suite | 1 + 3 passed | PASS |
| TC-4408 | Requirement PostgreSQL suites | 22 passed, including terminal Job replay and downgrade/re-upgrade | PASS |
| TC-4409 | privacy/log tests | Passed | PASS |
| TC-4410 | complete quality gates | Tests, lint, typecheck, build, validation and secret scan passed | PASS |

## Commands and Results

```text
pytest -q test_requirement_generation_application.py
                      PASS — 28 passed
TEST_DATABASE_URL=... pytest -q test_requirement_postgres.py test_requirement_generation_postgres.py
                      PASS — 22 passed
pytest -q apps/worker/tests/test_requirements_generation_task.py
                      PASS — 1 passed
node --test scripts/test/requirement-generation-contract.test.js
                      PASS — 3 passed
focused ruff          PASS
focused mypy          PASS — 11 source files
test:ci             PASS — 119 passed
test:eval           PASS — 8 passed
test:web            PASS — 19 passed
test:api            PASS — 334 passed with PostgreSQL integration enabled
test:worker         PASS — 57 passed after logging regression coverage
npm run lint        PASS
npm run typecheck   PASS — API 102 and Worker 25 Python source files; Web strict TypeScript
npm run build       PASS — Web production build plus API/Worker byte compilation
npm test            PASS
npm run validate    PASS
npm run scan:secrets
                      PASS — 522 publishable text files inspected
git diff --check    PASS — no whitespace errors; Windows line-ending notices only
```

## Final Status

**Final status:** PASS
