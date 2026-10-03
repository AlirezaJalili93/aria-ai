# Test Report: 0037 Usage Ledger

- Increment ID: `0037-usage-ledger`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

- Windows workspace, PowerShell
- Node/npm repository toolchain
- Python 3.12 API/Worker environments managed through `uv`
- Local PostgreSQL 16 Docker service at `127.0.0.1:5432`
- Workspace-local `UV_CACHE_DIR`; no external Provider or pricing service

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3701 | Migration | Inspect exact fields, precisions, indexes, RLS and FK actions | Contract matches; all FKs are RESTRICT |
| TC-3702 | Negative DB | Insert every invalid negative metric/cost or unknown status | DB constraint rejects each value |
| TC-3703 | Security/immutability | UPDATE or DELETE an inserted UsageRecord | Trigger rejects mutation |
| TC-3704 | Security | Inspect `aria_worker` attributes and grants | Non-super/non-bypass; only INSERT on Ledger |
| TC-3705 | Security/integration | Execute INSERT/SELECT/UPDATE/DELETE under `aria_worker` | INSERT succeeds; raw read/update/delete fail |
| TC-3706 | Retention | Hard-delete referenced Job, Project or Account | FK RESTRICT blocks deletion |
| TC-3707 | Unit/contract | Inspect/use Application port and Worker adapter | Append-only/provider-neutral; no Provider branching/public API |
| TC-3708 | Migration recovery | Downgrade to 0006 then re-upgrade head | Table/grant removed safely; durable role retained; upgrade succeeds |
| TC-3709 | Regression | Run repository quality gates | All tests, lint, types, builds and validators pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-3701–TC-3708 | Focused contract, Worker and PostgreSQL test commands | Contract 3 passed; Worker 1 passed; PostgreSQL 12 passed | PASS |
| TC-3709 | `node --test` contract suite | 99 passed | PASS |
| TC-3709 | `npm run test:web` | 18 passed | PASS |
| TC-3709 | `npm run test:api` with real `TEST_DATABASE_URL` | 194 passed | PASS |
| TC-3709 | `npm run test:worker` | 54 passed | PASS |
| TC-3709 | `npm run lint; npm run typecheck; npm run build` | All Web/API/Worker commands passed | PASS |
| TC-3709 | Final `npm test` and `npm run validate` | Development-record, contract, Web, API and Worker suites passed; architecture checks passed | PASS |
| TC-3709 | `git diff --check` | No whitespace error; only existing Windows LF→CRLF notices | PASS |

## Failures and Corrections

The required red phase failed because the migration and ports did not exist. After implementation,
the first static security assertion incorrectly matched the approved word `NOBYPASSRLS`; the test
was narrowed to reject only the positive privilege and then passed. Initial lint found import order
and two long test lines; both were corrected before the final run.

## Final Status

**Final status:** PASS
