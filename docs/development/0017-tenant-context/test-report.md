# Test Report: 0017 Tenant Context

- Increment ID: `0017-tenant-context`
- Date: 2026-08-25
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Python 3.12 project runtime through repository-pinned uv
- PostgreSQL integration through project-local loopback test cluster
- Node.js 24.11.1 / npm 11

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1701 | Dependency | Valid UUID and active Membership | Authorized Tenant Context with persisted role/status is returned |
| TC-1702 | API/Logging | Missing Header | 400 exact envelope; `tenant.context_rejected/missing`; no account trace |
| TC-1703 | API/Logging | Empty Header | 400 exact envelope; `tenant.context_rejected/empty`; no account trace |
| TC-1704 | API/Logging | Invalid UUID Header | 400 exact envelope; `tenant.context_rejected/invalid_uuid`; no raw value logged |
| TC-1705 | API/Security | Valid UUID without Membership/Account | Identical 403; `tenant.membership_denied/not_found`; no enumeration |
| TC-1706 | API/Security | invited Membership | Identical 403; `tenant.membership_denied/invited` |
| TC-1707 | API/Security | suspended Membership | Identical 403; `tenant.membership_denied/suspended` |
| TC-1708 | Security/Observability | Trace timing and dependency chain | account ID absent before resolver and present only after success |
| TC-1709 | Contract/Architecture | Inspect layering and Tenant Context | No SQL/framework/provider code in Application/API dependency |
| TC-1710 | PostgreSQL | Tenant A selects Account B | Existing composite lookup returns no Membership; access denied |
| TC-1711 | Regression | Run repository quality gates | Existing Web/API/Worker behavior remains passing |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-1701–TC-1709 | `node --test scripts/test/tenant-context-contract.test.js` and focused pytest suite | 4 contract tests and 23 focused API/Application tests passed | PASS |
| TC-1710 | PostgreSQL 18 on `127.0.0.1:55432`; `pytest -q -p no:cacheprovider apps/api/tests/test_account_bootstrap_postgres.py` | 10 passed; active selected Account resolved, Account owned by another subject denied as `not_found`, inactive states denied; test server stopped | PASS |
| TC-1711 | `npm run lint` | Web ESLint, API Ruff, and Worker Ruff passed | PASS |
| TC-1711 | `npm run typecheck` | Web TypeScript, API mypy (40 files), and Worker mypy (4 files) passed | PASS |
| TC-1701–TC-1709, TC-1711 | `npm run test:ci` | 41/41 contract and governance tests passed | PASS |
| TC-1701–TC-1708, TC-1711 | `npm run test:api` | 82 passed; 10 PostgreSQL tests skipped without `TEST_DATABASE_URL` as designed | PASS |
| TC-1711 | `npm run test:web`; `npm run test:worker` | 4 Web and 16 Worker tests passed | PASS |
| TC-1711 | `npm run build` | Next.js production build and Python API/Worker compilation passed | PASS |
| TC-1711 | `npm run scan:dependencies`; `npm run scan:secrets` | npm/API/Worker audits found no blocking vulnerability; 192 publishable text files passed secret scan | PASS |
| TC-1701–TC-1711 | `npm test`; `npm run validate` | Development-record gate, full test suites, and architecture validation passed | PASS |

## Failures and Corrections

- Initial contract/API tests failed because the Tenant Context modules and dependency did not exist;
  the implementation was then added behind Application ports.
- The first log assertions expected the `account_id` key to be absent. The versioned logger emits
  nullable trace fields, so assertions were corrected to require `account_id = null`; raw requested
  UUID values remain absent.
- Senior review exposed that the B02 active-Membership guard could pre-empt the approved
  `tenant.membership_denied` event for identities with only `invited` or `suspended` Memberships.
  A bootstrap-only dependency was introduced for S1-B04, while B02's operational guard remains
  unchanged. Dedicated regression cases now prove both inactive statuses reach the selected-Account
  resolver and remain denied.
- An initial dependency scan could not access uv's profile-level tool lock in the restricted shell.
  Re-running the same repository command with approved local tool access passed; no dependency or
  code change was used to bypass the scan.

## Final Status

**Final status:** PASS
