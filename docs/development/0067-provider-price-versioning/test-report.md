# Test Report: 0067 Provider Price Versioning

- Increment ID: `0067-provider-price-versioning`
- Date: 2026-09-20
- [Development record](./development.md)

## Environment

- Windows workspace and PowerShell
- Node.js/npm repository toolchain
- Python 3.12 API/Worker environments managed by `uv`
- Docker Desktop PostgreSQL 16 at `127.0.0.1:5432`
- Synthetic Provider/model/price fixtures only; no external Provider or customer data

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-6701 | Contract/Migration | Inspect Catalog fields, unique keys, rates, empty seed and Usage FK | Frozen contract is exact; no real prices |
| TC-6702 | Integration | Resolve prices before, at and after effective changes | Latest non-future version returned without tie |
| TC-6703 | Unit | Calculate mixed normal/cached/output token cost | Full Decimal precision; one eight-place HALF_UP rounding |
| TC-6704 | Negative | Negative counts/rates or cached input above total | Application and/or DB rejects input |
| TC-6705 | Security | Exercise Worker/public/API Catalog privileges and mutation trigger | Worker reads only; Runtime mutation denied; history immutable |
| TC-6706 | Migration | Upgrade a database containing historical unmatched Usage | Upgrade succeeds without rewriting history; new rows remain enforced |
| TC-6707 | Referential | Append Usage with missing or exact Price tuple | Missing tuple rejected; exact tuple accepted; delete restricted |
| TC-6708 | Regression | Full tests, static checks, builds and security scans | Repository gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-6701–TC-6707 | `node --test scripts/test/provider-price-versioning-contract.test.js` | 3 passed | PASS |
| TC-6703–TC-6704 | Worker focused unit tests | 8 passed | PASS |
| TC-6702 | Worker PostgreSQL resolver test | 1 passed | PASS |
| TC-6701, TC-6704–TC-6707 | API PostgreSQL Catalog + Usage tests | 18 passed | PASS |
| TC-6708 | `npm test` with local PostgreSQL | 917 passed, 1 environment-gated test skipped | PASS |
| TC-6708 | `npm run lint` | Web/API/Worker lint passed | PASS |
| TC-6708 | `npm run typecheck` | Web/API/Worker type checks passed | PASS |
| TC-6708 | `npm run build` | Web/API/Worker production/compile builds passed | PASS |
| TC-6708 | `npm run scan:secrets` | 803 publishable text files inspected; no finding | PASS |
| TC-6708 | `npm run scan:dependencies` outside sandbox | npm/API/Worker audits found no blocking vulnerabilities | PASS |
| TC-6708 | `npm run validate` | 23 architecture/documentation checks passed | PASS |
| TC-6708 | `git diff --check` | No whitespace errors | PASS |

## Failures and Corrections

- Contract-first tests initially failed because the migration, Application contract and adapter did
  not exist; implementation made them pass.
- The first PostgreSQL fixture passed timestamp strings to asyncpg; fixtures were corrected to use
  timezone-aware `datetime` values.
- The first downgrade used Alembic's naming-convention expansion for a raw-named check constraint;
  downgrade now drops both raw constraints by their exact names and downgrade/re-upgrade passes.
- The first dependency scan could not open the user-scoped `uv` tool lock inside the sandbox. It
  was rerun with approved external access and all three audits passed.
- A transient Windows build-isolation error occurred while reinstalling the local shared package;
  subsequent typecheck, full tests and builds all used the refreshed package and passed.
- The first architecture validation scanned a workspace-local `uv` cache and found two broken links
  inside third-party package metadata. The generated cache was removed and the clean validation
  passed all 23 checks.

## Final Status

**Final status:** PASS
