# Test Report: 0023 Context Source Model

- Increment ID: `0023-context-source-model`
- Date: 2026-09-02
- [Development record](./development.md)

## Environment

Windows/PowerShell; repository-pinned Node.js, Python 3.12/uv and PostgreSQL integration runtime.
Secrets are not recorded.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2301 | Domain | Construct Source and Version with approved fields | Exact fields and timezone-aware timestamps are preserved |
| TC-2302 | Domain/DB | Supported and unsupported vocabularies | Only four Source types, five Source states and four parse states pass |
| TC-2303 | Application/Scope | Request non-text source in S1-D01 | Rejected before persistence; file/message/URL remain unavailable |
| TC-2304 | Domain/DB/Repository | Version numbering and current lookup | Positive unique versions; greatest ready version is current |
| TC-2305 | Domain/DB | Ready Version without content or later mutation | Missing content rejected and ready snapshot cannot change |
| TC-2306 | Repository | Mark Source deleted then list/get normally | Source excluded; Version rows retained |
| TC-2307 | Observability | Run five lifecycle outcomes | Safe IDs/state/trace only; no raw/canonical/storage/metadata content |
| TC-2308 | Migration | Inspect exact M003 columns, FKs and indexes | Contract and tenant-first indexes match the approved schema |
| TC-2309 | PostgreSQL | Insert invalid type/status/parse status | Named DB checks reject each value |
| TC-2310 | PostgreSQL | Duplicate/non-positive Version and mixed ready states | Constraints reject invalid rows; MAX ready query is deterministic |
| TC-2311 | PostgreSQL | Update any ready Version field/state | Immutability trigger rejects mutation |
| TC-2312 | PostgreSQL | Hard-delete Source with Versions | RESTRICT blocks deletion; lifecycle delete preserves history |
| TC-2313 | PostgreSQL/Security | Cross-Account/Project Version linkage or missing creator | Composite FK/Profile FK rejects writes |
| TC-2314 | Failure/Privacy | Repository failure and private content | Stable failure event; content and storage reference absent |
| TC-2315 | PostgreSQL/Security | RLS/grants and downgrade/re-upgrade | RLS enabled, no Data API authority, recovery safe |
| TC-2316 | Contract | Search Increment for invented hash/limit/file activation | Deferred behaviors are absent |
| TC-2317 | Repository gate | Full test/build/validation/security suite | All mandatory gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2301–TC-2307, TC-2314 | Focused Node contract + Python Domain/Application tests | 4 contract and 10 Python tests passed | PASS |
| TC-2308–TC-2315 | PostgreSQL 18 on `127.0.0.1:55432`; focused M003 test module | 6 migration/repository/security tests passed | PASS |
| TC-2301–TC-2315 | Full API suite with `TEST_DATABASE_URL` on the isolated PostgreSQL cluster | 149 passed | PASS |
| TC-2301–TC-2316 | `npm run test:ci`, `npm run test:web`, `npm run test:worker` | 57 contract, 18 Web and 16 Worker tests passed | PASS |
| TC-2317 | `npm run lint`; `npm run typecheck`; Alembic offline upgrade SQL generation | All lint/type checks and complete migration SQL compilation passed | PASS |
| TC-2317 | `npm run build` | Next.js production build and Python compilation passed | PASS |
| TC-2307, TC-2314, TC-2317 | `npm run scan:secrets`; `npm run scan:dependencies` | 282 publishable files clean; npm/API/Worker audits found no blocking vulnerabilities | PASS |
| TC-2301–TC-2317 | `npm run quality` with the isolated PostgreSQL target | 246 tests passed; lint, typecheck, build and 22 architecture checks passed | PASS |

## Failures and Corrections

- Contract-first execution initially failed because the S1-D01 files did not exist; implementation
  then satisfied the deliberately red baseline.
- The first static event assertion expected three duplicated literal strings while production safely
  builds the approved event name from a bounded lifecycle outcome. The test was corrected to verify
  the shared formatter and each call site; all runtime event-name assertions also pass.
- The user-global uv cache/tool lock was inaccessible. Tests used ignored project-local
  `UV_CACHE_DIR`/`UV_TOOL_DIR`; the pinned dependency audit was rerun with approved network access.
- Alembic offline SQL compilation found one composite FK name and one index name beyond PostgreSQL's
  63-character identifier limit. Both were shortened without changing columns or semantics, and SQL
  generation plus the real migration then passed.
- The first full PostgreSQL suite showed the M002 schema test did not yet expect the new Project
  tuple-uniqueness index required by M003 tenant consistency. Its exact head-schema expectation was
  extended; the rerun passed all 149 API tests.
- Docker Desktop could not start under the available Windows service token. The already approved
  PostgreSQL 18 binary was used instead for a fresh, loopback-only temporary cluster.

## Final Status

**Final status:** PASS
