# Test Report: 0074 — Gap Detection Runtime Foundation

- [Development record](./development.md)

## Environment

- Windows, Python 3.12, Node.js 24.x and npm 11.x
- Docker Desktop PostgreSQL 16, isolated database `aria_0074_test_20260927`
- Fresh Migration head `0028_gap_detection_runtime`; downgrade/re-upgrade checked
- Deterministic Fake AI-03 Provider and synthetic fixture data only

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-7401 | Contract/Application | Internal scheduling, exact revision binding and zero Requirements | One atomic Job/Outbox pair; empty Requirement vector is valid |
| TC-7402 | Contract | Queue/Outbox envelope | Only the approved three identifiers cross the transport boundary |
| TC-7403 | Queue | Outbox publisher and controlled task | Canonical AI-03 task, automatic retry disabled |
| TC-7404 | Worker | Synthetic AI-03 and deterministic rules | Checklist-backed Gaps persist; no generic missing-Requirement Gap |
| TC-7405 | PostgreSQL | Atomic success | Gap/link/rule result and Job success commit together |
| TC-7406 | Recovery | Duplicate delivery and forced commit failure | No duplicate Gaps; same Job remains recoverable |
| TC-7407 | Privacy/Safety | Payload/log/composition leakage | No customer content, hosted registration or real Provider |
| TC-7408 | Architecture | No route/chaining/hosted activation | Deferred capabilities remain absent |
| TC-7409 | Quality | Full repository gates | Tests, lint, typecheck, build, validate and secret scan PASS |

## Execution Results

| ID | Command/evidence | Actual result | Status |
| --- | --- | --- | --- |
| TC-7401 | API scheduler unit and PostgreSQL tests | Empty Requirement vector persisted; one Job/Outbox; second active command rejected | PASS |
| TC-7402 | Runtime contract and message tests | Exact three-field Queue envelope; unapproved fields rejected | PASS |
| TC-7403 | Outbox publisher and controlled task tests | Canonical AI-03 task selected; automatic Queue retry disabled | PASS |
| TC-7404 | Synthetic adapter and Worker PostgreSQL tests | Three Checklist-backed Critical Gaps with zero Requirements; no generic missing-Requirement Gap | PASS |
| TC-7405 | PostgreSQL success test | Gaps, rule counts and Job success committed together | PASS |
| TC-7406 | Duplicate and forced-commit tests | Completed delivery suppressed; failed commit left zero Gaps and the same Job recoverable | PASS |
| TC-7407 | Contract/privacy tests and code review | No customer text or Provider payload in Queue/logs; hosted task absent | PASS |
| TC-7408 | Architecture scan and code review | No public route, chaining or real Provider activation | PASS |
| TC-7409 | Full repository gates | Test, lint, typecheck, build, secret scan and validation passed | PASS |

## Commands and Results

```text
npm run test:gap-detection-runtime
  PASS — 6 passed

focused API pytest / focused Worker pytest
  PASS — 24 / 16 passed

TEST_DATABASE_URL=... pytest -q -p no:cacheprovider
  apps/api/tests/test_gap_detection_jobs_postgres.py
  apps/api/tests/test_gap_detection_postgres.py
  apps/worker/tests/test_gap_detection_runtime_postgres.py
  PASS — API 12 and Worker 2 passed

alembic upgrade head
alembic downgrade 0027_requirement_gen_runtime
alembic upgrade head
alembic current
  PASS — 0028_gap_detection_runtime (head)

PostgreSQL privilege/RLS query on isolated database
  PASS — aria_worker Gap SELECT and named INSERT allowed;
         Gap UPDATE/DELETE and link DELETE denied; Gap RLS enabled

npm test
  PASS — CI 185, Eval 35, Web 40, API 447 passed/151 skipped,
         Worker 154 passed/16 skipped, plus increment contract suites
npm run lint
  PASS — Web ESLint and API/Worker Ruff
npm run typecheck
  PASS — Web TypeScript, API mypy 160 files, Worker mypy 62 files
npm run build
  PASS — Web production build and API/Worker byte compilation
npm run scan:secrets
  PASS — 901 publishable text files inspected
npm run validate
  PASS — final development-record and architecture validation
git diff --check
  PASS
```

The first PostgreSQL run failed because the test fixture attempted to insert a confirmed Fact
without SourceRef. The database correctly enforced the pre-existing provenance constraint. The
fixture was changed to `proposed`, and the isolated PostgreSQL suites passed on rerun.

## Final Status

**Final status:** PASS
