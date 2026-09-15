# Test Report: 0054 — Scope Draft Model

- **Status:** PASS
- **Increment:** S1-K01
- **Date:** 2026-09-12
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js and Python 3.12 repository pins
- PostgreSQL 16 local Docker runtime for integration tests
- No customer data, external Provider or production credentials

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-5401 | REQ-5401 | Migration/schema inventory | K01 table, constraints, indexes, RLS and grants exist | PASS |
| TC-5402 | REQ-5401 | Restrictive persistence | Tenant/Profile FKs use RESTRICT and duplicate Project/Version is rejected | PASS |
| TC-5403 | REQ-5402 | Twelve sections | All sections required structurally; empty values accepted | PASS |
| TC-5404 | REQ-5402 | Strict JSON contract | Unknown schema/section/nested shape is rejected | PASS |
| TC-5405 | REQ-5403 | Draft cardinality | One Draft per Project/Context Version | PASS |
| TC-5406 | REQ-5403 | Historical protection | Draft bound to older Context Version cannot mutate | PASS |
| TC-5407 | REQ-5404 | Trace tenant/version | Foreign tenant or Context Version trace is rejected | PASS |
| TC-5408 | REQ-5404 | Gap semantics | `resolved_gaps` cannot reference an open Gap | PASS |
| TC-5409 | REQ-5405 | CAS | Mismatched `expected_updated_at` returns conflict | PASS |
| TC-5410 | REQ-5405 | Actor invariant | User requires actor UUID; AI/system may be null | PASS |
| TC-5411 | REQ-5406 | Boundary/security | No public route or Data API authority is added | PASS |
| TC-5412 | REQ-5407 | Privacy | Content and raw trace payloads are absent from operational logs | PASS |
| TC-5413 | REQ-5408 | Scope boundary | K02/K03/K04/K05 behavior remains absent | PASS |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/scope-draft-contract.test.js` | 4/4 PASS | PASS |
| `npm run test:ci` | 149/149 PASS | PASS |
| `TEST_DATABASE_URL=... npm run test:api` | 447 passed, 2 warnings | PASS |
| `npm run lint:api` | All checks passed | PASS |
| `npm run typecheck:api` | No issues in 131 source files | PASS |
| `npm run test:records` | PASS | PASS |
| `npm run validate` | Architecture checks pass | PASS |
| `npm run scan:secrets` | PASS | PASS |
| `git diff --check` | PASS | PASS |
| `npm test` | records 6/6; CI 149/149; Eval 35/35; Web 31/31; API 447 passed (2 warnings); Worker 57 passed (1 warning) | PASS |

## Senior Verification

Migration chain reached `0017_scope_drafts` during PostgreSQL integration. The K01 validator and
repository preserve tenant isolation, Context-Version binding, structured content and safe actor
metadata without exposing Scope content. Readiness and Snapshot behavior were not implemented.
The full repository test command completed successfully; the only warnings are existing FastAPI/httpx
and pytest cache-permission warnings and do not affect test outcomes.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
