# Test Report: 0080 Worker Restart and Redelivery E2E

- **Increment ID:** `0080-worker-restart-redelivery-e2e`
- **Date:** 2026-09-28
- [Development record](./development.md)

## Environment

Windows host, Python 3.12 Worker/API environments, Docker-backed PostgreSQL 16 and Redis 7,
Celery 5.6.3, pre-migrated dedicated `aria_0077_test` database and local Redis DB 15. Worker #1
and #2 use the actual product Celery configuration with a test-only five-second visibility timeout
and Windows `solo` pool. No real Provider or customer data.

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-8001 | E2E/Recovery | Hard-kill Worker #1 after durable running and restart Worker #2 | Unacknowledged task is redelivered and same Job succeeds |
| TC-8002 | Contract | Deterministic failpoint is reached before Provider boundary | Pre-crash Provider/Usage counts are zero |
| TC-8003 | Integration | Advisory lock is held while Worker #1 lives and reclaimed only after session death | No concurrent execution; same running Job is recoverable |
| TC-8004 | E2E/Idempotency | Verify durable identities and committed effects after recovery | Same Job/Event, one Provider invocation, one UsageRecord, one Context Version, no duplicates |
| TC-8005 | Security | Inspect envelope/log/process output and activation boundary | Identifier-only delivery; no fixture/customer/Provider secret leakage; Hosted remains disabled |
| TC-8006 | Regression | Run repository quality gates | `npm test` and `npm run validate` pass with completed records |

## Execution Results

| ID | Command or steps | Actual result | Status |
| --- | --- | --- | --- |
| TC-8001 | `npm run test:worker-restart-e2e` | Worker #1 hard-killed at checkpoint; same unacknowledged task redelivered; original Job succeeded | PASS |
| TC-8002 | 0080 pre-crash assertion | Job=`running`, attempt=1, Outbox=`published`; Provider markers=0, Usage=0, Context effects=0 | PASS |
| TC-8003 | 0080 concurrent lock probe and Worker #2 recovery | Probe received `already_in_progress`; after process death Worker #2 reacquired and completed | PASS |
| TC-8004 | 0080 final SQL/file assertions | One Job/Event, one invocation/Usage attempt, one Context Version/Item, duplicate effects=0 | PASS |
| TC-8005 | Contract/leakage assertions and process-output scan | Identifier-only path; no synthetic source marker in Worker output; Hosted composition unchanged | PASS |
| TC-8006 | `npm test` | Contract/Eval/Web PASS; API 610 passed/1 Hosted-only skip; Worker 188 passed | PASS |
| TC-8006 | `npm run lint`; `npm run typecheck`; `npm run build`; `npm run scan:secrets` | PASS; mypy API 164 and Worker 69 files; secret scan 948 files | PASS |
| TC-8006 | `npm run validate` | Architecture and completed-record validation passed | PASS |

## Failures and Corrections

- First fresh-secondary-database run failed before 0080 execution because migration 0030 attempted
  to recreate the cluster-global `aria_generation_lock_owner` Role. The partially migrated
  throwaway database was removed; the final Gate ran against the existing fully migrated,
  dedicated synthetic E2E database. No migration behavior was silently changed.
- The first pre-crash assertion used one bind parameter in both UUID and JSON-text comparisons;
  asyncpg rejected the mixed type with `ProgrammingError`. Separate UUID/text binds corrected the
  diagnostic query, and the complete Gate then passed.
- Initial lint/typecheck/build invocations could not access the global `uv` cache under the
  filesystem sandbox. Re-running with the repository's ignored `.uv-cache` passed without a code
  or dependency change.

## Final Status

**Final status:** PASS
