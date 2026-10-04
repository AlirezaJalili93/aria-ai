# Test Report: 0089 Authenticated Scope Share Management API

- Increment ID: `0089-authenticated-scope-share-management-api`
- Date: 2026-10-04
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Docker PostgreSQL 16
- Isolated database: `aria_0089_test`
- Real Provider/customer content: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-8901 | REQ-8901 | Authenticated exact-version Create returns 201 and one raw token | PASS |
| TC-8902 | REQ-8902 | Same key and canonical payload return the same ID with no token and `replayed=true` | PASS |
| TC-8903 | REQ-8902 | Changed expiry or target under the same key returns `IDEMPOTENCY_CONFLICT` | PASS |
| TC-8904 | REQ-8903 | Concurrent same-key commands commit one Share Link and disclose one token | PASS |
| TC-8905 | REQ-8903 | Share-Link constraint failure rolls back its idempotency reservation | PASS |
| TC-8906 | REQ-8904 | Active roles and Member creator restriction enforce tenant-safe visibility | PASS |
| TC-8907 | REQ-8905 | Exactly-empty Revoke and same-target replay return 204 with one terminal transition | PASS |
| TC-8908 | REQ-8906 | Raw token/hash/Scope content are absent from store, replay, errors and logs | PASS |
| TC-8909 | all | Full PostgreSQL-backed tests, lint, typecheck, build and validation pass | PASS |

## Commands and Results

```text
npm run test:scope-share-management
PASS — 4 contract tests

pytest focused Sharing Application and authenticated HTTP route
PASS — 11 tests

pytest Scope Share-Link PostgreSQL gate with TEST_DATABASE_URL=aria_0089_test
PASS — 6 tests

npm test with TEST_DATABASE_URL=aria_0089_test
PASS — 208 CI/contract, 35 Eval, 40 Web, 646 API (1 skipped), 242 Worker (2 skipped)

npm run lint / npm run typecheck / npm run build
PASS

npm run validate
PASS — architecture, OpenAPI and development-record checks
```

## Execution Results

- The first Create response exposed one 43-character unpadded Base64URL token; replay returned the
  same Share Link ID with `token=null` and `token_available=false`.
- Concurrent same-key transactions produced one Share Link, one completed safe idempotency outcome
  and only one disclosed token.
- A forced database constraint failure rolled back both Share-Link and idempotency state.
- Revoke required an empty body, remained terminal, and replayed as 204 without another transition.
- Changed target/payload fingerprints conflicted without creating additional rows.
- Tenant/role checks returned the existing outward-safe not-found behavior for invisible targets.

## Security and Leakage Evidence

- Idempotency persistence contains only `scope_share_link_id`; raw token, token hash and first
  response are absent.
- Public/API response models do not expose Account ID, creator internals, token hash or Scope
  snapshot content.
- Structured Sharing events emit identifiers and bounded outcome data only.
- PostgreSQL access remains through the controlled server repository; no public/anon grant was
  added.
- Tests use synthetic identities, timestamps and Scope snapshots only.

## Final Status

**Final status:** PASS

0089 completes authenticated, one-time-disclosure Share-Link Create and terminal idempotent Revoke.
It does not implement Share URL construction, browser bootstrap, Guest Session, UI, Approval,
Change Request, Preview sharing or authenticated Share listing.
