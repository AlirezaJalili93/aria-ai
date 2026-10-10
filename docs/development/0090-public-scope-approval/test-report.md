# Test Report: 0090 Public Scope Approval

- Increment ID: `0090-public-scope-approval`
- Date: 2026-10-04
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Docker PostgreSQL 16
- Isolated database: `aria_0090_test`
- Real Provider/customer content: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9001 | REQ-9001 | Public endpoint requires the exact body and mandatory `Idempotency-Key` | PASS |
| TC-9002 | REQ-9001, REQ-9005 | First Approval returns 201; same-key replay returns 200 and the identical business result | PASS |
| TC-9003 | REQ-9002 | Guest name is NFC-normalized/trimmed and bounded; controls and non-literal consent are rejected | PASS |
| TC-9004 | REQ-9003 | Approval persists the exact Scope Version ID, version number and `version_hash` | PASS |
| TC-9005 | REQ-9003, REQ-9006 | Public response excludes `version_hash`, token/hash and internal tenant data | PASS |
| TC-9006 | REQ-9004 | Approval, idempotency outcome and Scope Version status commit atomically | PASS |
| TC-9007 | REQ-9004 | Forced transaction failure leaves no Approval and preserves `awaiting_approval` | PASS |
| TC-9008 | REQ-9005 | Changed semantics under one key conflict; concurrent different keys create one Approval | PASS |
| TC-9009 | REQ-9006 | Capability failures are safe 404 and logs contain no token, hash, Scope or guest content | PASS |
| TC-9010 | all | Full PostgreSQL-backed tests, lint, typecheck, build and validation pass | PASS |

## Commands and Results

```text
npm run test:public-scope-approval
PASS — 4 contract tests

pytest focused Domain, Application and public HTTP route
PASS — 16 tests

pytest Scope Approval PostgreSQL gate with TEST_DATABASE_URL=aria_0090_test
PASS — 4 tests

npm test with TEST_DATABASE_URL=aria_0090_test
PASS — 208 CI/contract, 35 Eval, 40 Web, 666 API (1 skipped), 242 Worker (2 skipped)

npm run lint / npm run typecheck / npm run build
PASS

npm run validate
PASS — architecture, OpenAPI and development-record checks
```

## Execution Results

- The first successful command created one immutable Approval, captured the exact Scope Version hash
  and moved only that Scope Version to `approved`.
- Replay returned the same Approval ID, Scope Version number, normalized guest name and approval time
  without adding another row or transition.
- Reusing a key with changed canonical semantics returned `IDEMPOTENCY_CONFLICT`.
- Concurrent different-key requests relied on the database uniqueness guard and produced exactly one
  Approval.
- A forced transaction error rolled back Approval and retained the original Scope Version status.
- Project status and Share-Link revocation state remained unchanged.

## Security and Leakage Evidence

- Approval and guest idempotency persistence contain no raw capability token.
- Public response models omit `version_hash`, token hash, Account ID and creator internals.
- Request-body logging remains disabled/redacted for the public Share routes and responses are
  `no-store`.
- The Approval table has RLS enabled and grants no direct access to public, anonymous or
  authenticated database roles.
- Tests use synthetic identities, names, timestamps and Scope snapshots only.

## Final Status

**Final status:** PASS

0090 completes public, capability-authorized, idempotent final Approval of one exact immutable Scope
Version. It does not implement Change Requests, verified Guest identity, Approval UI, public editing
or automatic Share-Link revocation.
