# Test Report: 0072 Context Structuring Command API & Controlled Synthetic E2E

- Increment ID: `0072-context-structuring-command-synthetic-e2e`
- Date: 2026-09-22
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Python 3.12 API/Worker environments managed by `uv`
- Node.js/npm repository toolchain
- Docker Desktop PostgreSQL 16 on localhost
- Dedicated disposable database `aria_0072_test_20260922`
- Deterministic Fake Provider and synthetic fixture only
- Real Provider credentials, customer content and Hosted activation prohibited

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-7201 | API contract | Valid authenticated exactly empty command | Exact 202 payload and scheduled command |
| TC-7202 | API negative | Missing/empty headers or any body bytes | Existing auth/tenant semantics or 422 validation |
| TC-7203 | Application/PostgreSQL | Missing/cross-tenant Project | Safe not-found before idempotency probing |
| TC-7204 | Application/PostgreSQL | Exact replay and concurrent new command | Replay wins; new active command conflicts |
| TC-7205 | API contract | Frozen application failures | Exact 403/404/409/422 mappings |
| TC-7206 | Configuration/API | Feature disabled/default/Hosted | Fail-closed 403; Hosted enable rejected |
| TC-7207 | Security | Flag enabled without explicit synthetic authorization | No Job/Outbox/Provider execution |
| TC-7208 | Controlled E2E | HTTP through Relay/Celery/Worker/Fake/finalization | One Job succeeds with atomic Context Version |
| TC-7209 | Static/security | Runtime composition and logs | No real Provider/customer/Hosted activation or content leakage |
| TC-7210 | Safety | General database supplied to E2E | Rejected before migration/reset |
| TC-7211 | Repository gate | Full test/lint/typecheck/build/validation/security checks | PASS |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-7201–TC-7207 | Focused API/application/PostgreSQL suites | 22 unit/API tests and 4 PostgreSQL tests passed; final API file rerun: 16 passed | PASS |
| TC-7208 | `npm run test:context-structuring-e2e` with dedicated database | Fresh migrations `0000` through `0026`; `CONTROLLED_SYNTHETIC_E2E=PASS` | PASS |
| TC-7209 | `npm run test:context-structuring-runtime` | 6 contract/security/static tests passed | PASS |
| TC-7210 | Negative guarded invocation with `aria_local` | `DEDICATED_DATABASE_GUARD=PASS`; no migration/reset performed | PASS |
| TC-7211 | `npm test` | API: 590 passed/1 skipped; Worker: 146 passed/1 skipped; Web, contract and Eval suites passed | PASS |
| TC-7211 | `npm run lint` | Web ESLint and API/Worker Ruff passed | PASS |
| TC-7211 | `npm run typecheck` | Web strict TypeScript; API 156 and Worker 52 Python modules passed | PASS |
| TC-7211 | `npm run build` | Next.js production build plus API/Worker compile builds passed | PASS |
| TC-7211 | `npm run scan:dependencies` | npm/API/Worker scans found no blocking vulnerability | PASS |
| TC-7211 | `npm run scan:secrets` | 865 publishable text files inspected; no finding after correction | PASS |
| TC-7211 | `npm run validate` | Architecture and completed development-record validation passed | PASS |
| TC-7211 | `git diff --check` | No whitespace error | PASS |

## Failures and Corrections

- The first root `npm test` attempt was blocked only by sandbox access to the user-scoped `uv`
  cache. The exact command was rerun with approved tool access and all suites passed.
- Early E2E construction exposed Python import-path and async connection-pool loop mismatches.
  Workspace package paths and process/loop ownership were made explicit before the final run.
- Senior review added an assertion that Relay/Celery preserves `outbox_event_id`, not only `job_id`.
- The initial Secret scan rejected a credential-shaped test-only PostgreSQL URL. It was replaced
  with the repository's credential-free example URL; the focused API test and scan then passed.
- Senior review found that the initial harness reset whichever `TEST_DATABASE_URL` was supplied.
  Both E2E processes now reject any database not explicitly named `aria_0072_test...`; the negative
  guard and the complete fresh-database E2E both passed.
- A Starlette/httpx deprecation warning and a sandbox-only pytest cache warning were observed. They
  do not change test outcomes or the 0072 contract.

## Deferred Verification

- No real-provider quality, customer-content, Hosted AI, Primary/Fallback or paid-call recovery
  claim is made by this report.
- Product AI Acceptance remains blocked on its separately approved data/evaluation/release gates.

## Final Status

**Final status:** PASS
