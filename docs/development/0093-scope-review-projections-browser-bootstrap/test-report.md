# Test Report: 0093 Scope Review Projections and Secure Browser Bootstrap

- Increment ID: `0093-scope-review-projections-browser-bootstrap`
- Date: 2026-10-05
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- PostgreSQL 16 integration database: isolated `aria_0093_test`
- Customer content / real Provider: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9301 | REQ-9301, REQ-9306 | Share projection is exact-version, allowlisted and creator-filtered for Member | PASS |
| TC-9302 | REQ-9302, REQ-9306 | Decision projection returns none/approval/change_request without secret hashes | PASS |
| TC-9303 | REQ-9303 | Public resolve reports exact bound-Version decision status | PASS |
| TC-9304 | REQ-9304 | Fragment is validated and replaced before resolve; token remains volatile only | PASS |
| TC-9305 | REQ-9305 | Static Persian title and no live title lookup or 0094 controls | PASS |
| TC-9306 | REQ-9301, REQ-9303 | PostgreSQL queries remain tenant/project/version scoped | PASS |
| TC-9307 | REQ-9302, REQ-9306 | Comment/token/hash content is absent from telemetry and forbidden responses | PASS |
| TC-9308 | REQ-9304, REQ-9306 | Negative source tests prohibit browser persistence, query/path token and analytics-before-clear | PASS |
| TC-9309 | all | Full tests, lint, typecheck, build and validation pass | PASS |

## Commands and Results

```text
npm run test:scope-review-projections
PASS — 3 contract tests

pytest focused Application/API/Public resolver
PASS — 29 tests

pytest test_scope_share_link_postgres.py with TEST_DATABASE_URL=aria_0093_test
PASS — 7 PostgreSQL integration tests

npm test
PASS — CI 213; Eval 35; Web 43; API 527 passed / 175 environment-gated skipped;
       Worker 208 passed / 36 environment-gated skipped

npm run lint
PASS — Web ESLint; API and Worker Ruff

npm run typecheck
PASS — Web, API and Worker type checks

npm run build
PASS — production Web/API/Worker build; /scope-review generated

npm run validate
PASS — repository validation completed
```

The focused PostgreSQL suite ran against the isolated database. Full-suite skips are declared
environment-specific hosted/integration gates outside 0093; no 0093 test was skipped.

## Execution Results

- Owner/Admin received all exact-Version Share links; Member received only links created by that
  actor. Active/expired/revoked status and `can_revoke` were server-derived.
- Authenticated Decision returned the exact Version's none or Change Request projection, including
  comment only in the authorized response.
- An old ShareLink continued resolving Version 1 and reported `superseded` after Version 2 existed.
- Browser bootstrap removed the fragment before its no-store POST and retained no capability after
  completion, cleanup or refresh.
- Production build generated `/scope-review` with the static Persian title and no 0094 controls.

## Security and Leakage Evidence

- PostgreSQL queries include account, project and exact scope-version identities; deleted Projects
  remain invisible and Member link rows are creator-filtered.
- The historical public resolver returned `superseded` from its bound Version after Version 2 was
  created; it did not resolve latest.
- API response negative tests exclude raw token, token hash, version hash, creator and Account
  internals; observability tests prove Change Request comment is response-only.
- Browser source tests prohibit local/session storage, IndexedDB, cookies, token path/query,
  Analytics and console diagnostics; `replaceState` occurs before resolve.

## Final Status

**Final status:** PASS
