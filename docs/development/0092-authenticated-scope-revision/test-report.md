# Test Report: 0092 Authenticated Scope Revision

- Increment ID: `0092-authenticated-scope-revision`
- Date: 2026-10-05
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Docker PostgreSQL 16
- Isolated database: `aria_0092_test`
- Real Provider/customer content: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9201 | REQ-9201, REQ-9205 | N+1 created with exact lineage; N superseded; exact replay returns same N+1 | PASS |
| TC-9202 | REQ-9202 | Paired lineage, composite FKs, uniqueness and immutability are DB-enforced | PASS |
| TC-9203 | REQ-9203 | Different-key race produces one revision and one stale loser | PASS |
| TC-9204 | REQ-9204, REQ-9205 | Safe 404 and distinct stale/CAS/readiness/unchanged/idempotency responses | PASS |
| TC-9205 | REQ-9201, REQ-9206 | Generic K05 cannot create over latest changes_requested Version | PASS |
| TC-9206 | REQ-9202 | Partial or mutable lineage is rejected | PASS |
| TC-9207 | REQ-9203 | Failed N+1 insertion rolls back and retains N=changes_requested | PASS |
| TC-9208 | REQ-9207 | Historical Share Link remains bound to N; no excluded side effects or leakage | PASS |
| TC-9209 | all | Full tests, lint, typecheck, build and validation pass | PASS |

## Commands and Results

```text
npm run test:scope-revision
PASS — 5 contract tests

pytest focused Domain/Application/API
PASS — 17 tests

pytest tests/test_scope_revision_postgres.py with TEST_DATABASE_URL=aria_0092_test
PASS — 4 tests

npm test
PASS — CI 213; Eval 35; Web 40; API 695 passed / 1 skipped; Worker 242 passed / 2 skipped

npm run lint
PASS — API and Worker Ruff checks

npm run typecheck
PASS — Web, API and Worker type checks

npm run build
PASS — production build completed

npm run validate
PASS — repository validation completed
```

The three skipped full-suite tests are pre-existing environment-specific gates outside 0092. All
0092 Domain, Application, API, migration, PostgreSQL concurrency, rollback and security tests
executed.

## Execution Results

- The first command created exactly one N+1 ScopeVersion with the exact parent and Change Request
  lineage, then superseded N in the same transaction.
- Exact same-key replay returned the original N+1 after N was superseded; changed semantics
  returned the idempotency conflict without another Version.
- Concurrent different-key commands consumed the Change Request once and returned the stable stale
  outcome to the loser.
- A forced N+1 insertion failure rolled back supersession and left N in `changes_requested`.
- Generic K05 creation could not bypass required revision lineage, while historical Share Links
  remained bound to N.

## Security and Leakage Evidence

- Revision queries are account/project scoped and cross-tenant targets use safe not-found behavior.
- Composite FKs bind parent and Change Request to the same Tenant/Project and exact target Version.
- RLS remains enabled; no Data API grant or policy was added.
- Logs and response DTOs exclude Draft/snapshot content, Change Request comment and version hash.

## Final Status

**Final status:** PASS
