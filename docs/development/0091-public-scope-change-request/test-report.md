# Test Report: 0091 Public Scope Change Request

- Increment ID: `0091-public-scope-change-request`
- Date: 2026-10-05
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Docker PostgreSQL 16
- Isolated database: `aria_0091_test`
- Real Provider/customer content: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9101 | REQ-9101, REQ-9105 | Independent immutable row captures exact ScopeVersion/link/version/hash and no new version | PASS |
| TC-9102 | REQ-9102 | Concurrent Approval and Change Request produce exactly one terminal decision | PASS |
| TC-9103 | REQ-9103 | Comment uses NFC/LF/trim, preserves internal structure and enforces 1–4000/control rules | PASS |
| TC-9104 | REQ-9104, REQ-9106 | Exact public body/header contract returns 201 first, 200 replay and no comment/hash exposure | PASS |
| TC-9105 | REQ-9101, REQ-9107 | Composite FKs, uniqueness, immutable trigger and snapshot lineage are DB-enforced | PASS |
| TC-9106 | REQ-9102 | Race loser receives `SCOPE_ALREADY_APPROVED` or `SCOPE_CHANGES_ALREADY_REQUESTED` | PASS |
| TC-9107 | REQ-9104 | Same-key changed request conflicts; invalid capabilities are safe 404 | PASS |
| TC-9108 | REQ-9105 | Transaction changes only ScopeVersion status; Project/ShareLink and version count remain unchanged | PASS |
| TC-9109 | REQ-9106 | Response/logs exclude comment, guest name, raw token/hash, version hash and Scope content | PASS |
| TC-9110 | REQ-9107 | RLS is enabled and public/anon/authenticated have no direct table access | PASS |
| TC-9111 | all | Full tests, lint, typecheck, build and architecture/documentation validation pass | PASS |

## Commands and Results

```text
npm run test:public-scope-change-request
PASS — 4 contract tests

pytest focused Domain, Application and public HTTP route
PASS — 15 tests

pytest 0091 plus sharing/security PostgreSQL gates with TEST_DATABASE_URL=aria_0091_test
PASS — 17 tests

npm test with TEST_DATABASE_URL=aria_0091_test
PASS — 208 CI/contract, 35 Eval, 40 Web, 685 API (1 skipped), 242 Worker (2 skipped)

npm run lint / npm run typecheck / npm run build
PASS

npm run validate
PASS — architecture, OpenAPI and development-record checks
```

The three skipped full-suite tests are pre-existing environment-specific gates outside 0091. All
0091 Domain, Application, API, migration, PostgreSQL race, rollback and security tests executed.

## Execution Results

- First success created one immutable Change Request, captured the exact ScopeVersion hash and
  moved only that ScopeVersion to `changes_requested`.
- Same-key canonical replay returned the original business result without a second row or state
  transition; changed semantics conflicted.
- A real concurrent Approval/Change Request race committed one terminal outcome and returned the
  winner-specific stable error to the loser.
- Forced transaction failure left no Change Request and retained `awaiting_approval`.
- Project state, ShareLink revocation and ScopeVersion cardinality remained unchanged.

## Security and Leakage Evidence

- Persistence contains no raw capability token; hash resolution remains internal to the existing
  ShareLink aggregate.
- Public DTOs omit comment, `version_hash`, token/hash, Account ID and creator internals.
- Public Share middleware sets `Cache-Control: no-store`; structured events contain only bounded
  operational identifiers/outcomes.
- `scope_change_requests` has RLS enabled, immutable-row protection and no public, anonymous or
  authenticated grants.
- Tests use synthetic names, comments, identities and snapshots only.

## Final Status

**Final status:** PASS

0091 completes public, capability-authorized and idempotent Change Request recording for one exact
immutable Scope Version. Authenticated revision, replacement ScopeVersion creation, automatic
regeneration, Guest identity verification and UI remain outside this increment.
