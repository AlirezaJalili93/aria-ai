# Test Report: 0038 Context Item Schema

- Increment ID: `0038-context-item-schema`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

- Windows workspace, PowerShell
- Node/npm repository toolchain
- Python 3.12 API environment managed through `uv`
- Local PostgreSQL 16 Docker service at `127.0.0.1:5432`
- No external Provider, Context-generation workflow or Data API client

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3801 | Migration | Inspect exact fields, numeric precision, indexes, RLS and FK actions | Canonical schema; all parent FKs RESTRICT |
| TC-3802 | Domain/DB | Use every accepted vocabulary and preserve content verbatim | Values accepted; content unchanged |
| TC-3803 | Negative Domain/DB | Invalid version/vocabulary/confidence/creator/evidence/JSON shape | Declared validation or DB constraint rejects |
| TC-3804 | Domain | Whole-Version and half-open offset forms | Both/none offsets accepted; partial/invalid range rejected |
| TC-3805 | Application | Validate each Source Reference before a confirmed Fact persist | Only semantically valid references commit |
| TC-3806 | Repository/PostgreSQL | Resolve missing, cross-tenant, mismatched or non-ready Source Version | Invalid targets return no provenance |
| TC-3807 | Retention/Tenancy | Cross-tenant Project link and hard deletion of referenced parents | Composite/RESTRICT FKs block operation |
| TC-3808 | Security | Inspect RLS and Data API grants | RLS enabled; anon/authenticated receive no privileges |
| TC-3809 | Architecture | Inspect Domain/Application/API surface and deferred terms | Boundaries clean; no content logging, API, UI, normalization or Context Version table |
| TC-3810 | Migration recovery | Downgrade to 0007 then re-upgrade head | Context Item table removed and recreated safely |
| TC-3811 | Regression | Run repository quality gates | Tests, lint, types, builds and validators pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-3801–TC-3810 | Focused contract, Domain, Application and PostgreSQL tests | Contract 3 passed; Domain/Application 16 passed; PostgreSQL 16 passed | PASS |
| TC-3811 | `npm run test:ci` | 102 passed | PASS |
| TC-3811 | `npm run test:web` | 18 passed | PASS |
| TC-3811 | `npm run test:api` with real `TEST_DATABASE_URL` | 226 passed | PASS |
| TC-3811 | `npm run test:worker` | 54 passed | PASS |
| TC-3811 | `npm run lint; npm run typecheck; npm run build` | All Web/API/Worker commands passed | PASS |
| TC-3811 | Final `npm test` and `npm run validate` | Development records, all suites and architecture checks passed | PASS |
| TC-3811 | `git diff --check` | No whitespace errors | PASS |

## Failures and Corrections

The required Red phase failed because the migration and Context Item boundaries did not exist.
During real PostgreSQL verification, a non-array JSON value reached `jsonb_array_length` before the
separate type check and produced a function error. The confirmed-Fact constraint was guarded with a
`CASE`, after which all focused PostgreSQL tests passed through a real downgrade/re-upgrade cycle.
Pytest also reported a non-failing local cache write warning and an upstream TestClient deprecation
warning; neither changed test execution or product behavior.

## Final Status

**Final status:** PASS
