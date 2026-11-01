# Test Report: 0060 — Operational Dashboard

- **Status:** PASS
- **Increment:** S1-L02
- **Date:** 2026-09-13
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js repository pin 24.11.1
- Python 3.12 repository pin via workspace UV runner
- PostgreSQL 16 local Docker service for migration/privilege/view evidence
- OpenTelemetry 1.44.0 dependency family; no external telemetry credential or customer data

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6001 | REQ-6001 | Complete staging OTLP configuration | Adapter is created with explicit endpoint, headers, timeout, interval and capacity | PASS |
| TC-6002 | REQ-6001 | Direct OTLP configured for Production | Settings reject the staging-only topology | PASS |
| TC-6003 | REQ-6002 | Metrics backend raises during API request | HTTP response remains successful | PASS |
| TC-6004 | REQ-6002 | Metrics backend raises during Worker execution | Handler and Job completion remain successful | PASS |
| TC-6005 | REQ-6003 | HTTP instrumentation | Count and duration use method/status class/route template | PASS |
| TC-6006 | REQ-6003 | D2 dashboard parse/query inspection | Request, 5xx, p50, p95 and p99 panels exist | PASS |
| TC-6007 | REQ-6004 | Worker and Outbox paths | Success/failure and duration/publish outcomes are emitted without payload | PASS |
| TC-6008 | REQ-6004 | D3 dashboard parse/query inspection | DB Job/Outbox state and bounded runtime metrics are visible | PASS |
| TC-6009 | REQ-6005 | Usage commit and validation rejection | Provider/cost and schema/business counters use safe dimensions | PASS |
| TC-6010 | REQ-6005 | Cost-by-project panel | Query reads private aggregate view; project is not a metric label | PASS |
| TC-6011 | REQ-6006 | Seed one aged queued Job | One view snapshot returns count=1 and age >= seeded interval | PASS |
| TC-6012 | REQ-6006 | Static source inspection | No Redis count is named canonical queue depth | PASS |
| TC-6013 | REQ-6007 | Observer privilege query and role execution | Views are readable; public base Jobs table is denied | PASS |
| TC-6014 | REQ-6007 | Data API grants and migration recovery | anon/authenticated have no views; downgrade/re-upgrade passes and preserves role | PASS |
| TC-6015 | REQ-6008 | Raw ID path, unknown field, UUID and unapproved model | Metric record is rejected/dropped | PASS |
| TC-6016 | REQ-6008 | Static leakage vocabulary scan | Customer content, prompt, response and resource IDs are not metric dimensions | PASS |
| TC-6017 | REQ-6009 | Parse three dashboard files | JSON and schema/version metadata are valid | PASS |
| TC-6018 | REQ-6009 | Import same JSON twice | Stable unique UID and identical parsed payload prevent duplicate dashboards | PASS |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/operational-dashboard-contract.test.js` | 6 passed | PASS |
| Focused API/Worker operational tests | 13 passed | PASS |
| PostgreSQL operational dashboard integration tests | 3 passed | PASS |
| `npm run test:ci` | 170 passed | PASS |
| `npm run test:eval` | 35 passed | PASS |
| `npm run test:web` | 35 passed | PASS |
| `npm run lint` | Web ESLint and API/Worker Ruff passed | PASS |
| `npm run typecheck` | Web TypeScript plus API 143-file and Worker 28-file strict mypy passed | PASS |
| `npm run test:api` with local PostgreSQL | 500 passed | PASS |
| `npm run test:worker` | 58 passed | PASS |
| `npm run build` | Web production build and API/Worker compile passed | PASS |
| `npm run scan:secrets` | 734 publishable text files inspected; no findings | PASS |
| `git diff --check` | No whitespace errors | PASS |
| `npm test` with local PostgreSQL | 6 records + 170 contract + 35 eval + 35 Web + 500 API + 58 Worker passed | PASS |
| `npm run validate` | Architecture and development-record checks passed | PASS |

## Senior Verification

Senior review verified fail-open behavior, bounded cardinality, PostgreSQL truth, least privilege,
downgrade recovery, dashboard identity, explicit configuration and deferred alert/Production scope.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
