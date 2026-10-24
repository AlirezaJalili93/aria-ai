# Test Report: 0088 Public Scope Share Resolution

- Increment ID: `0088-public-scope-share-resolution`
- Date: 2026-10-04
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Docker PostgreSQL 16
- Isolated database: `aria_0088_test`
- Real Provider/customer content: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-8801 | REQ-8801/8804/8805 | Public POST succeeds without JWT/header and returns only exact snapshot DTO with no-store | PASS |
| TC-8802 | REQ-8801/8803/8805 | Invalid request shape is 422; malformed and unknown capabilities are identical 404; all are no-store | PASS |
| TC-8803 | REQ-8802 | Only canonical 32-byte unpadded Base64URL reaches one SHA-256 repository lookup | PASS |
| TC-8804 | REQ-8803 | Unknown, expired, revoked and inaccessible bound resources are the same not-found outcome | PASS |
| TC-8805 | REQ-8804 | A newer Scope Version does not repoint an existing Share Link | PASS |
| TC-8806 | REQ-8806 | Shared resolve lock blocks concurrent revoke; revoke succeeds after resolve transaction ends | PASS |
| TC-8807 | REQ-8807 | RLS/no-policy/no-direct-grant foundation remains enforced | PASS |
| TC-8808 | REQ-8808 | Raw token/hash/snapshot are absent from logs; path/query/GET are not capability transports | PASS |
| TC-8809 | all | Full lint, typecheck, build, repository tests and architecture validation pass | PASS |

## Commands and Results

```text
npm run test:public-scope-share
PASS — 5 contract tests

pytest focused public resolver and HTTP route
PASS — 13 tests

pytest Scope Share Link PostgreSQL gate with TEST_DATABASE_URL=aria_0088_test
PASS — 4 tests

Focused Ruff / Mypy
PASS

npm test
PASS — 208 CI/contract, 35 Eval, 40 Web, 638 API (1 skipped), 242 Worker (2 skipped)

npm run lint / npm run typecheck / npm run build
PASS

npm run validate
PASS — 23 architecture/documentation checks
```

## Execution Results

- Valid capability lookup returned Scope Version 1 after Version 2 was inserted.
- Unknown, expired, revoked and soft-deleted/inaccessible lineage all failed closed.
- A shared resolution lock blocked an exclusive revoke lock; after release, revocation committed and
  later resolution returned not found.
- HTTP 200, 404 and 422 responses carried `Cache-Control: no-store`.
- Strict body validation rejected missing/null/extra properties without invoking the resolver.

## Security and Leakage Evidence

- Tokens are accepted only in the JSON body and never in the endpoint path or query contract.
- Application and request logs contain neither raw token nor SHA-256 token hash nor snapshot data.
- Response DTO contains no Account, Project, Share Link, Scope Version ID, creator or lifecycle data.
- Direct Data API access remains denied; resolution uses the controlled server repository path.
- Tests use synthetic identifiers and Scope content only.

## Final Status

**Final status:** PASS

0088 completes public read-only resolution of one immutable Scope Version. It does not implement
approval, change requests, public editing, guest identity/session, Share UI or Preview sharing.
