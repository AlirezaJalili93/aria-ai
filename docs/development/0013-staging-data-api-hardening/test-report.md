# Test Report: Staging Data API Hardening

- Increment ID: `0013-staging-data-api-hardening`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Local OS: Windows; branch from hosted M001 merge SHA `143e566e7a2363b879091805d168d6df2228d114`.
- Local integration target: temporary PostgreSQL 18 with simulated `anon` and `authenticated` roles.
- Hosted finding source: Supabase Staging `hqgfqlvfwflbazsuhazs`, PostgreSQL 17.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1301 | Contract | Inspect the immutable follow-up revision | Correct down-revision; version-table RLS; conditional current/default revoke; no policy/service-role behavior |
| TC-1302 | Integration/Security | Apply with simulated provider roles, inspect RLS/grants/migration-owner default ACL, downgrade and re-upgrade | RLS is enabled; current Data API grants and migration-owner defaults are absent at head; chain remains reversible in tests |
| TC-1303 | Repository gate | Run complete quality, dependency, and secret gates | All tests/builds/checks pass with no blocking vulnerability or credential |
| TC-1304 | Governance | Run `npm test` and `npm run validate` with completed records | Mandatory gates pass and no applied revision changed |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-1301 | `npm run test:ci` | 32/32 passed, including the immutable follow-up hardening contract | PASS |
| TC-1302 | `npm run test:api` with real `TEST_DATABASE_URL`; controlled runner; direct PostgreSQL readback | 72/72 passed; downgrade/re-upgrade passed; exact head reported; version-table RLS=`true`; current grant count=0; migration-owner default ACL test=0 | PASS |
| TC-1303 | `npm run quality`; dependency scan; secret scan | 128 tests, all builds and 22 architecture checks passed; no blocking dependency issue; no committed credential | PASS |
| TC-1304 | `npm test`; `npm run validate`; `git diff --check` | Mandatory test/validator gates and patch hygiene passed; prior shared revisions have no diff | PASS |

## Failures and Corrections

1. Hosted post-M001 inspection exposed the implicit Supabase grants and RLS-disabled version table;
   this revision is the forward correction and leaves the applied M001 file unchanged.
2. Senior documentation review found the prior increment's aggregate test count recorded as 122;
   the actual six suites totalled 126. The evidence text was corrected without changing test status.
3. Hosted readback after merge showed that the Supabase-owned `supabase_admin` default ACL remains;
   the local default-ACL assertion only proves the migration owner's defaults. Current hosted table
   grants remain zero. Increment 0014 records the provider-owned forward-risk guardrail.

## Final Status

**Final status:** PASS
