# Test Report: 0020 Project Domain Repository

- Increment ID: `0020-project-domain-repository`
- Date: 2026-09-01
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Repository-pinned Python 3.12/uv and Node.js/npm runtimes
- PostgreSQL integration through `TEST_DATABASE_URL`

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2001 | Domain | Supported Project type/status | Exact documented vocabulary accepted |
| TC-2002 | Domain | Unsupported type/status or title over 255 | Rejected without normalization assumptions |
| TC-2003 | Application | Active Tenant owner creates Project | Owner equals authenticated subject and Account matches context |
| TC-2004 | Application/Security | invited/suspended context creates Project | Rejected before repository write |
| TC-2005 | PostgreSQL | Insert Project without Context version | Value is 0; negative value rejected |
| TC-2006 | PostgreSQL | Status default/constraint | `draft` default; unsupported status rejected |
| TC-2007 | Repository | Read/list soft-deleted Project | Ordinary methods do not return it |
| TC-2008 | Repository/Security | Cross-tenant UUID and explicit recovery read | Cross-tenant ordinary read misses; only explicit including-deleted method recovers own row |
| TC-2009 | Migration | Inspect FKs/indexes | Approved constraints and three tenant-first indexes exist |
| TC-2010 | PostgreSQL | Update accounts/profiles/projects | DB trigger advances `updated_at` consistently |
| TC-2011 | Observability | Create/update/archive/delete and repository failure | Safe event names and IDs; no title/content/JWT/subject |
| TC-2012 | PostgreSQL/Security | Inspect RLS/grants and downgrade/re-upgrade | RLS on; no Data API authority; migration remains recoverable |
| TC-2013 | Regression | Full repository gates | `npm test` and `npm run validate` pass |
| TC-2014 | Application | Empty update or member sets archived through general update | Rejected before repository mutation |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node scripts/run-uv.mjs --project apps/api run pytest -q -p no:cacheprovider apps/api/tests/test_project_domain.py apps/api/tests/test_project_application.py` | 15 Project Domain/Application tests passed | PASS |
| `node --test scripts/test/project-domain-contract.test.js` | 4 Project architecture/migration contracts passed | PASS |
| `npm run test:api` with `TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:55432/postgres` | 121 passed on PostgreSQL 18, including 6 M002 tests and the full migration chain | PASS |
| `npm run lint` | Web ESLint and API/Worker Ruff checks passed | PASS |
| `npm run typecheck` | Web TypeScript and API/Worker mypy checks passed | PASS |
| `npm run build` | Next.js production build plus API/Worker compile passed | PASS |
| `npm run test:worker` | 16 passed | PASS |
| `npm run scan:secrets` | 239 publishable text files inspected; no finding | PASS |
| `npm run scan:dependencies` | No blocking npm/API/Worker vulnerability | PASS |
| `npm test` with real `TEST_DATABASE_URL` | 6 record + 49 contract + 12 Web + 121 API + 16 Worker tests passed | PASS |
| `npm run validate` | All 22 architecture/record checks passed | PASS |

## Failures and Corrections

- Contract-first tests initially failed because M002 and the Project module did not yet exist.
- Mypy then found that the new persistence input referenced a non-persisted `deleted_at`; the
  Infrastructure mapper was corrected and the full suite rerun.
- A senior-review test was initially placed outside its async scenario and failed collection; the
  test was corrected before any PASS result was recorded.

## Final Status

**Final status:** PASS
