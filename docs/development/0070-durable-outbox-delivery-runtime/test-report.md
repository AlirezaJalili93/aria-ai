# Test Report: 0070 Durable Outbox Delivery Runtime

- Increment ID: `0070-durable-outbox-delivery-runtime`
- Date: 2026-09-21
- [Development record](./development.md)

## Environment

- Windows workspace and PowerShell
- Node.js/npm repository toolchain
- Python 3.12 API/Worker environments managed by `uv`
- Docker Desktop PostgreSQL 16 and Redis 7 on localhost
- Dedicated database `aria_0070_test_20260921`; no existing local database was truncated
- Redis test queue uses isolated DB 15 and a unique Queue name removed after the test
- No Hosted deployment, customer data or external Provider call

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-7001 | Contract | Inspect explicit channels, task mapping and process mode | Only approved route/task exists; frozen constants present |
| TC-7002 | PostgreSQL | Two relays claim the same eligible batch concurrently | Each event is claimed once; domain events are ignored |
| TC-7003 | PostgreSQL | Inspect committed claim, poll before expiry, poll after expiry | Claim is externally visible; unavailable before expiry; same event reclaimed after expiry |
| TC-7004 | Unit | Publish failures across attempt sequence and extreme attempt value | Delays are 2/4/8/16/32/60 and safely capped without terminal failure |
| TC-7005 | Unit/PostgreSQL | Unknown job-queue event | No publish; durable blocked state; never automatically eligible again |
| TC-7006 | Recovery | Publish succeeds but acknowledgement fails; deliver completed Job twice | Lease replay remains possible; second consumer execution is successful no-op |
| TC-7007 | Unit | Translate approved Outbox payload | Exact minimal Parser envelope and fixed task/Queue; no SDK retry |
| TC-7008 | Redis | Broker unavailable then available | First publish fails safely; same logical event publishes after recovery |
| TC-7009 | Security/PostgreSQL | Inspect Worker grants and RLS | SELECT plus column-level delivery UPDATE; no payload UPDATE/INSERT/DELETE |
| TC-7010 | Security | Inspect lifecycle logs with sensitive payload marker | Required metadata exists; payload/customer marker absent |
| TC-7011 | Architecture | Run static boundary tests and build | Celery remains Infrastructure-only; no new deployable/hosted activation |
| TC-7012 | Regression | Full repository tests, lint, typecheck, build, validation | All gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-7001, TC-7010–TC-7011 | `npm run test:outbox-runtime` and updated TXT/Celery contract suites | All focused contract tests passed | PASS |
| TC-7002–TC-7006, TC-7009 | Focused Worker PostgreSQL suites on dedicated database | Concurrent claim, lease recovery, role, duplicate consumer and atomic parser tests passed | PASS |
| TC-7008 | Real Redis outage/recovery integration test | Unavailable endpoint failed safely; recovered broker accepted exactly one queued message | PASS |
| TC-7001–TC-7009 | Focused Worker unit/integration suite | Outbox/Publisher/Parser tests passed | PASS |
| TC-7009 | Migration from empty PostgreSQL database through `0025_outbox_delivery_runtime` | Full chain installed; expected head verified | PASS |
| TC-7012 | `npm run lint` | Web/API/Worker lint passed after one line-length correction | PASS |
| TC-7012 | `npm run typecheck` | Web/API/Worker strict type checks passed | PASS |
| TC-7012 | `npm run build` | Web production build and API/Worker compile builds passed | PASS |
| TC-7012 | `npm test` | 982 tests passed; one unrelated Hosted-environment test skipped | PASS |
| TC-7010–TC-7012 | `npm run scan:secrets` | No secret finding | PASS |
| TC-7012 | `npm run validate` | Architecture and development-record gates passed | PASS |
| TC-7012 | `git diff --check` | No whitespace errors | PASS |

## Failures and Corrections

- Sandboxed Python initially could not access the user-scoped `uv` cache; the approved external
  tool access was used for project gates.
- The first combined lint run found one 101-character SQL line; it was split and lint passed.
- The first final regression invocation supplied a plain PostgreSQL test DSN; one existing Worker
  test passes that value directly to SQLAlchemy and attempted the unavailable synchronous
  `psycopg2` driver. The complete suite was rerun with the correct `postgresql+asyncpg` scheme and
  passed. No product code was changed for this environment-only invocation error.
- The first full contract regression correctly found an obsolete S1-E02 assertion that allowed
  exactly one Celery import. Registration was moved out of Tasks into Queue Infrastructure and the
  boundary test was superseded to require every Celery import to remain in that Infrastructure.
- Senior review found table-wide Worker UPDATE broader than necessary. Migration 0025 now grants
  only exact delivery-state columns; a new clean database and privilege test verified the result.
- Reapplying an edited migration to the existing six-day-old local database would have required a
  destructive Outbox reset. That action was rejected and not bypassed. A separate database was
  created and migrated from empty instead, preserving all existing data.

## Deferred Verification

- Hosted Relay activation and runtime topology are not claimed.
- `domain_event` delivery is not implemented or tested as a transport.
- Automatic task retry, dead-letter/exhaustion and operational unblock tooling remain deferred.

## Final Status

**Final status:** PASS
