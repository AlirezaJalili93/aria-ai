# Test Report: 0011 Account Bootstrap

- Increment ID: `0011-account-bootstrap`
- Date: 2026-08-24
- [Development record](./development.md)

## Environment

- Windows 11 / PowerShell
- Python 3.12 repository pin with uv 0.12.5
- Isolated temporary PostgreSQL 18.0 integration instance bound to loopback with a clean
  `aria_test` database
- PostgreSQL 16 service configured as the CI integration target
- Node.js 24.11.1 / npm repository pins
- No hosted credential, JWT, Email, external subject, or Profile data is used as test evidence.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-1101 | Application/Integration | First verified identity request | One Profile, Account, active Owner Membership are returned |
| TC-1102 | Migration/Integration | Insert Profile/Account without optional values | DB applies `locale='fa-IR'`, generates Account UUID; Email column is absent |
| TC-1103 | Application/Constraint | Existing suspended Membership | Operational bootstrap context is denied; Membership remains stored and suspended |
| TC-1104 | Application/Integration | Repeat bootstrap request | Existing Context resolves with zero INSERT/UPDATE writes |
| TC-1105 | PostgreSQL concurrency | Two simultaneous requests for one new subject | Profile PK conflict gate yields exactly one Profile, Account, Membership |
| TC-1106 | Application/PostgreSQL | Failure between aggregate writes | Entire Profile/Account/Membership transaction rolls back |
| TC-1107 | Architecture | Dependency boundary scan | API has no SQLAlchemy; Application has no FastAPI/SQLAlchemy; Domain has no framework imports |
| TC-1108 | API/Logging | First and existing bootstrap requests | started + completed/resolved events contain only safe fields |
| TC-1109 | API/Logging | Bootstrap exception | failed event is emitted without JWT, Email, raw subject, Profile data, or exception payload |
| TC-1110 | API contract | Implicit bootstrap dependency | JWT verifier precedes bootstrap use case; no `/bootstrap` or `/me` route exists |
| TC-1111 | Migration | Upgrade empty PostgreSQL database to head | M000/M001 tables, checks, uniqueness, indexes, and defaults exist |
| TC-1112 | Migration | Downgrade identity revision and re-upgrade | Non-destructive rollback removes identity tables and chain re-applies cleanly |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-1101 | API unit + real PostgreSQL first-request tests | One Profile, Account, active Owner Membership created | PASS |
| TC-1102 | M001 schema inspection and default inserts | Exact Profile fields; no Email; DB returned `fa-IR` and generated Account UUID | PASS |
| TC-1103 | Suspended integration case + invalid `disabled` insert | Access denied, row retained; DB rejected `disabled` | PASS |
| TC-1104 | Repeat test with PostgreSQL `xmin` comparison | Same Context resolved; all three row versions unchanged | PASS |
| TC-1105 | Two `asyncio.gather` requests on real PostgreSQL | One creator, one resolver; aggregate row counts all equal one | PASS |
| TC-1106 | Forced duplicate Account PK during bootstrap | Integrity failure observed; Profile/Membership rolled back | PASS |
| TC-1107 | `npm run test:ci` layering contract + type/lint gates | Boundaries preserved; 26 contract tests passed | PASS |
| TC-1108 | Dependency event tests for create/resolve | Approved started + completed/resolved events emitted safely | PASS |
| TC-1109 | Dependency failure tests and serialized-log assertions | Stable failed event; prohibited identity/content values absent | PASS |
| TC-1110 | Dependency override + route inspection tests | JWT precedes use case; neither prohibited route exists | PASS |
| TC-1111 | Alembic upgrade on clean PostgreSQL + schema inspection | Tables, defaults, checks, uniqueness, indexes, and RLS present | PASS |
| TC-1112 | Alembic downgrade to M000 then upgrade to head | Identity tables removed and reapplied successfully | PASS |

## Command Summary

- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test:ci` — 27 passed.
- `npm run test:web` — 4 passed.
- `npm run test:api` with `TEST_DATABASE_URL` — 71 passed; one upstream deprecation warning and one
  non-functional sandbox cache warning.
- `npm run test:worker` — 14 passed, one non-functional pytest cache-permission warning.
- `npm run build` — PASS.
- `npm run scan:dependencies` — PASS; no blocking vulnerabilities.
- `npm run scan:secrets` — PASS; 166 publishable text files inspected after temporary
  test-database cleanup.
- Final aggregate `npm run quality` — PASS.
- `npm test` — PASS; 122 total tests across records, contracts, Web, API, and Worker.
- `npm run validate` — PASS; 22 architecture and development-record checks passed.

## Failures and Corrections

1. Contract-first Red run failed collection with two missing `account_bootstrap` modules. This was the
   expected pre-implementation evidence.
2. The initial PostgreSQL integration run exposed two issues: double-prefixed check-constraint names
   and a Membership insert reaching PostgreSQL before its Account FK target. Base constraint names
   and an explicit Account flush corrected both defects.
3. The rollback test intentionally produces a duplicate Account primary-key error. The test confirms
   that the surrounding transaction leaves no Profile or Membership behind.
4. Senior review found the canonical Account UUID database default missing from M001. The migration,
   model, contract test, and real PostgreSQL default-insert test were corrected before the final run.
5. The first dependency-scan attempt could not write uv's user-level tool lock from the sandbox.
   Moving uv's tool/cache paths into the Workspace and rerunning with advisory-network access
   completed successfully; npm, API, and Worker reported no blocking vulnerabilities.
6. The first final `npm run quality` run found one 101-character test line. The assertion was wrapped
   without behavioral change and the complete quality gate was rerun.

## Final Status

**Final status:** PASS

This PASS covers the S1-B02 cases above and the repository-wide required gates. Hosted Supabase
schema application is intentionally not claimed; this increment proves the versioned migration on
isolated PostgreSQL and configures PostgreSQL 16 as the CI target.
