# Test Report: 0087 Scope Share-Link Foundation

- Increment ID: `0087-scope-share-link-foundation`
- Date: 2026-10-03
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Docker PostgreSQL 16
- Isolated database: `aria_0087_test`
- Real Provider/customer content: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-8701 | REQ-8701/8702 | Token is random 32-byte Base64URL without padding; only its SHA-256 digest persists | PASS |
| TC-8702 | REQ-8703 | Non-future expiry is rejected and access checks expiry synchronously | PASS |
| TC-8703 | REQ-8703 | Revoke is terminal; replay adds no second write; reactivation/delete fail in DB | PASS |
| TC-8704 | REQ-8704/8706 | Composite FK rejects cross-Account/Project ScopeVersion linkage | PASS |
| TC-8705 | REQ-8705 | Create/revoke permission matrix and outward-safe member/cross-tenant denial pass | PASS |
| TC-8706 | REQ-8706 | Four FKs are RESTRICT; RLS is on; `anon/authenticated` grants and exact-ID probe are denied | PASS |
| TC-8707 | REQ-8702/8707 | Schema/logs contain no raw token, hash emission, snapshot or customer content | PASS |
| TC-8708 | REQ-8708 | No guest/public route, UI or public resolver is introduced | PASS |
| TC-8709 | all | Full API regression, lint, typecheck, build, repository tests and architecture validation pass | PASS |

## Commands and Results

```text
npm run test:scope-share-link
PASS — 5 contract tests

pytest focused Scope Share Link domain/application
PASS — 9 tests

pytest Scope Share Link PostgreSQL gate with TEST_DATABASE_URL=aria_0087_test
PASS — 2 tests

pytest complete API suite with TEST_DATABASE_URL=aria_0087_test
PASS — 623 passed, 1 skipped

npm run lint:api / npm run typecheck:api / npm run build:api
PASS

npm test / npm run validate
PASS — final repository gates
```

## Execution Results

- Migration 0034 applied on clean PostgreSQL and exposed one immutable tenant-scoped table.
- Create returned one public token while the database retained exactly its 32-byte digest.
- Cross-tenant ScopeVersion binding and revocation attempts failed without existence disclosure.
- A Member could revoke only their own link; an Admin could revoke a Project link.
- Duplicate revoke returned the same terminal row without a second persistence mutation.
- RLS/grant catalog checks and the direct `authenticated` role probe failed closed.

## Security and Leakage Evidence

- The raw token is absent from schema, repository entities, operational events and error fields.
- Token hash, Scope snapshot/content and customer text are absent from event emission.
- All exact resource lookups include current Account and Project constraints.
- No FK uses CASCADE; Share Link deletion is rejected by a database trigger.
- Tests use synthetic identifiers/data only.

## Final Status

**Final status:** PASS

0087 completes only the secure Domain/Application/persistence foundation. Guest resolution, public
rendering and HTTP exposure remain deferred and are not represented as passed capabilities.
