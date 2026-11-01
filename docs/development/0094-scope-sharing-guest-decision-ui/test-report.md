# Test Report: 0094 Scope Sharing and Guest Decision UI

- Increment ID: `0094-scope-sharing-guest-decision-ui`
- Date: 2026-10-10
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- PostgreSQL 16 isolated local database: `aria_0094_test`
- Customer content / real Provider: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9401 | REQ-9401 | Public DTO contains only section_id/value recursively | PASS |
| TC-9402 | REQ-9402 | New Share on superseded Version is rejected; historical resolve still works | PASS |
| TC-9403 | REQ-9403 | Authenticated exact-version Share Settings uses existing APIs | PASS |
| TC-9404 | REQ-9404 | Token URL is one-time, memory-only and copied only by explicit gesture | PASS |
| TC-9405 | REQ-9405 | All twelve sections and four decision states render without live title lookup | PASS |
| TC-9406 | REQ-9406, REQ-9407 | Guest decisions validate bounded fields, confirmation and stable retry keys | PASS |
| TC-9407 | REQ-9403, REQ-9405, REQ-9408 | Web type/lint/test/build and responsive tokenized source checks pass | PASS |
| TC-9408 | REQ-9401, REQ-9404, REQ-9406, REQ-9407, REQ-9408 | Negative leakage/storage/lineage tests pass | PASS |
| TC-9409 | REQ-9402 | Isolated PostgreSQL transaction/race boundary tests pass | PASS |
| TC-9410 | all | Full npm test and validate gates pass | PASS |

## Commands and Results

```text
Focused API tests
PASS — 30 tests

pytest test_scope_share_link_postgres.py with TEST_DATABASE_URL=aria_0094_test
PASS — 7 tests

npm run typecheck:web
PASS

npm run lint:web
PASS

npm run test:web
PASS — 47 tests

npm test
PASS — CI 213; Eval 35; Web 47; API 528 passed / 175 environment-gated skipped;
       Worker 208 passed / 36 environment-gated skipped

npm run lint
PASS — Web ESLint; API and Worker Ruff

npm run typecheck
PASS — Web, API and Worker type checks

npm run build
PASS — production Web/API/Worker build; authenticated Share route and /scope-review generated

npm run validate
PASS — repository validation completed
```

## Security and Leakage Evidence

- Public projection validation rejects trace, provenance arrays, item IDs and extra nested fields.
- Existing historical links resolve the exact superseded Version; server rejects a new Share for it.
- Browser source contains no local/session storage, IndexedDB, cookie, console or Analytics path.
- Guest token/input/idempotency state is retained on retryable failures and cleared only after a
  successful terminal mutation or component teardown.

## Execution Results

- Authenticated Share Settings loaded exact-Version status, link projections and the final decision
  in parallel, without exposing token/hash/creator internals to the browser.
- Create returned a one-time fragment URL only for the initial response; replay rendered the
  documented revoke-and-recreate recovery without reconstructing a capability.
- Public Review rendered all twelve allowlisted sections and restricted mutations to
  `awaiting_approval`.
- Approval and Change Request reused their Idempotency-Key across the same retry, rotated it only
  when canonical form input changed, and preserved volatile input/capability after retryable error.
- PostgreSQL rejected new link creation after the exact Version became superseded while an existing
  historical link continued to resolve that immutable Version.

## Final Status

**Final status:** PASS
