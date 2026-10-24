# Test Report: 0025 Text Context API

- Increment ID: `0025-text-context-api`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

Windows/PowerShell; repository-pinned Node.js and Python 3.12/uv; PostgreSQL 18 temporary loopback
cluster on `127.0.0.1:55433`. `TEST_DATABASE_URL` and other credentials are not recorded.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2501 | API/Contract | Submit authenticated tenant request with exact text body and key | Standard `202` envelope returns source/status/job identifiers and request ID |
| TC-2502 | API/Auth/Error | Omit Auth, Account context or key; send invalid body; map conflict/not-found | Stable `401/400/422/409/404` behavior without resource disclosure |
| TC-2503 | Domain/Boundary | Blank, whitespace, control chars, NUL, 50,000/50,001 characters and Persian whitespace | Only approved inputs pass; accepted text remains byte-equivalent after UTF-8 encoding |
| TC-2504 | Application/PostgreSQL | Persist valid exact text pipeline | Source/Version/Job/Outbox/idempotency outcome commits once; payloads/logs contain no text |
| TC-2505 | Idempotency | Repeat same key/input; change text or Project with same key | Same result replayed; changed complete input returns `IDEMPOTENCY_CONFLICT` |
| TC-2506 | PostgreSQL/Time/Scope | Reuse key by another actor and after 24-hour expiry | Actor scope is independent; expired reservation is safely replaced |
| TC-2507 | Migration/Security | Inspect columns/FKs/unique/RLS/grants; downgrade and re-upgrade | Exact schema, fail-closed Data API and safe recovery all pass |
| TC-2508 | Transaction/Tenant | Target missing/cross-tenant Project | Safe not-found and all reserved/pipeline writes rollback |
| TC-2509 | Privacy/Logging | Inspect Job/Outbox refs and structured events | No raw/canonical text, storage URL, payload body or idempotency key appears |
| TC-2510 | Repository gate | Run contracts, lint/typecheck, builds and architecture validation | All mandatory repository gates pass |
| TC-2511 | Scope/Architecture | Inspect dependencies and forbidden implementation choices | No parser, file API, queue provider, relay or retry/backoff policy is added |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2501–TC-2505, TC-2508–TC-2509 | Focused Domain/Application/API suite | 21 tests passed | PASS |
| TC-2504–TC-2508 | `pytest apps/api/tests/test_text_context_postgres.py -vv` with PostgreSQL 18 | 4 integration tests passed | PASS |
| TC-2501, TC-2505, TC-2510–TC-2511 | `node --test scripts/test/text-context-api-contract.test.js` | 3 contract tests passed | PASS |
| TC-2507, TC-2510 | Alembic `upgrade head --sql` with explicit API config | Full chain through `0006_idempotency_records` compiled | PASS |
| TC-2501–TC-2511 | `npm run quality` with real `TEST_DATABASE_URL` | Lint/typecheck passed; 63 contract, 18 Web, 176 API and 16 Worker tests passed; production build and 22 architecture checks passed | PASS |
| TC-2509–TC-2510 | `npm run scan:secrets` | 310 publishable text files inspected; no secret finding | PASS |
| TC-2510 | `npm run scan:dependencies` | npm, API and Worker scans found no blocking vulnerabilities | PASS |

## Failures and Corrections

- The first exact-checksum unit fixture used an incorrect manually calculated digest. The
  implementation result was independently recomputed, the fixture corrected, and the complete
  boundary suite passed.
- The first PostgreSQL replay test reused one pooled async Engine across two separate Windows event
  loops and failed with `Event loop is closed`. The harness was corrected so each Engine is created,
  used and disposed within one loop; all four PostgreSQL tests then passed without connection-loop
  warnings.
- The first dependency scan was blocked by sandbox access to the shared uv tool lock. It was rerun
  with explicit permission; npm, API and Worker audits then passed with no blocking vulnerability.

## Final Status

**Final status:** PASS
