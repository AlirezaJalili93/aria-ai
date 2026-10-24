# Test Report: 0024 Jobs and Outbox Persistence

- Increment ID: `0024-jobs-outbox-persistence`
- Date: 2026-09-02
- [Development record](./development.md)

## Environment

Windows/PowerShell; repository-pinned Node.js and Python 3.12/uv; PostgreSQL 18 temporary loopback
cluster on `127.0.0.1:55433`. Secrets are not recorded.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2401 | Domain/DB | Construct tenant/system Jobs and invalid attempts/status | Current fields/states accepted; invalid values and Project-without-Account rejected |
| TC-2402 | Domain | Exercise documented Job transitions | Only queued-to-running/cancelled and running-to-terminal pass |
| TC-2403 | Application/Privacy | Schedule success and repository failure | One commit on success; stable safe events; payload/key absent from logs |
| TC-2404 | Migration | Inspect exact columns, FKs, checks and indexes | Logical M008 matches current Data Dictionary vocabulary |
| TC-2405 | PostgreSQL/Security | Link Job to another Account's Project | Composite tenant FK rejects write |
| TC-2406 | PostgreSQL/Transaction | Commit Job+Outbox; fail second write; mutate payload | Both commit together, rollback together, payload update rejected |
| TC-2407 | PostgreSQL/Security | Inspect RLS/grants and downgrade/re-upgrade | RLS enabled, Data API fail-closed, recovery safe |
| TC-2408 | Contract/Architecture | Inspect dependencies and forbidden transport choices | Domain independent; no queue adapter/retry policy introduced |
| TC-2409 | Repository gate | Run full test/build/validation/security suite | All mandatory gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2401–TC-2403 | Focused Python tests as part of API suite without the new PostgreSQL module | 129 tests passed, including new Domain/Application tests | PASS |
| TC-2404–TC-2408 | `node --test scripts/test/jobs-outbox-contract.test.js` | 3 contract tests passed | PASS |
| TC-2404–TC-2407 | Focused API run with PostgreSQL 18 test target | 133 tests passed, including 4 Jobs/Outbox integration tests | PASS |
| TC-2401–TC-2408 | Full API suite with `TEST_DATABASE_URL` | 158 tests passed | PASS |
| TC-2408–TC-2409 | `npm run lint`; `npm run typecheck`; `npm run test:ci`; Web/Worker tests | Lint/typecheck passed; 60 contract, 18 Web and 16 Worker tests passed | PASS |
| TC-2404, TC-2407, TC-2409 | Alembic offline full-chain SQL generation | Complete chain through `0005_jobs_outbox` compiled | PASS |
| TC-2409 | `npm run build` | Next.js production build and Python compilation passed | PASS |
| TC-2401–TC-2409 | `npm run quality` with isolated PostgreSQL target | Final seal recorded after documentation finalization | PASS |

## Failures and Corrections

- The first PostgreSQL start command quoted its `-o` options as one port value and was rejected.
  The same loopback-only cluster was started with corrected argument quoting; no schema action had
  occurred before the correction.
- The first Alembic offline command was launched from repository root without `script_location` and
  failed after all PostgreSQL tests had passed. The final verification will run it with the explicit
  API Alembic configuration.

## Final Status

**Final status:** PASS
