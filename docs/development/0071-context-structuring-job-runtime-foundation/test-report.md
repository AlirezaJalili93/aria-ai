# Test Report: 0071 Context Structuring Job Runtime Foundation

- Increment ID: `0071-context-structuring-job-runtime-foundation`
- Date: 2026-09-21
- [Development record](./development.md)

## Environment

- Windows workspace and PowerShell
- Node.js/npm repository toolchain
- Python 3.12 API/Worker environments managed by `uv`
- Docker Desktop PostgreSQL 16 on localhost
- Dedicated database `aria_0071_test_20260921`; no existing local database was truncated
- Synthetic fixtures and deterministic Fake Provider only
- No Hosted deployment, customer data, external Provider or paid call

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-7101 | Unit/Contract | Schedule valid explicit AI-01 command | Exact Job/Event/channel and `job_id + status_url` result |
| TC-7102 | Unit/PostgreSQL | Replay same key; reuse key with different command | Same Job/no new rows; conflict rejected |
| TC-7103 | PostgreSQL | Two schedulers race on same Project | Exactly one active Job; loser receives declared conflict |
| TC-7104 | Unit/Contract | Publish approved Outbox event | Exact task and three-field Queue envelope; no automatic retry |
| TC-7105 | Unit | Execute through provider-neutral guard | Duplicate running/completed delivery is suppressed/no-op |
| TC-7106 | Unit/PostgreSQL | Resolve AI-01 Job and latest ready Source snapshot | Same-tenant state only; deterministic synthetic result |
| TC-7107 | PostgreSQL | Successful AI-01 finalization | Context Item, Project Version and succeeded Job commit together |
| TC-7108 | Recovery/PostgreSQL | Force final commit failure then recover | No partial business state; same running Job safely succeeds with Fake |
| TC-7109 | PostgreSQL | Deliver completed Job again | No second Context Item/Version/Usage append |
| TC-7110 | Security/Migration | Inspect/use Worker grants and RLS | Only required Project column update and AI Context insert allowed |
| TC-7111 | Security/Architecture | Inspect composition/logs with sensitive marker | No public/Hosted activation and no content leakage |
| TC-7112 | Regression | Full lint/typecheck/tests/build/validation | All repository gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-7101–TC-7103 | API focused unit plus dedicated PostgreSQL scheduler tests | Unit scenarios passed; exact replay retained one Job/Event; concurrent race retained one active Job | PASS |
| TC-7104–TC-7109, TC-7111 | Worker focused unit and PostgreSQL runtime tests | Message/task/Fake/consumer tests passed; atomic success, rollback recovery and duplicate no-op verified | PASS |
| TC-7110 | Fresh database upgrade to 0026, downgrade to 0025, re-upgrade; role probe | Clean chain and rollback/re-upgrade passed; allowed reads/version update/AI insert passed; title update denied | PASS |
| TC-7111 | `npm run test:context-structuring-runtime` | 5 static contract/security/activation tests passed | PASS |
| TC-7112 | `npm run lint` | Web, API and Worker lint passed | PASS |
| TC-7112 | `npm run typecheck` | Web strict TypeScript plus API 155 and Worker 52 Python modules passed | PASS |
| TC-7112 | Full component test suites, then final `npm test` | 998 component tests passed; two environment-gated tests skipped; final aggregate including record gate passed | PASS |
| TC-7112 | `npm run build` | Web production build and API/Worker compile builds passed | PASS |
| TC-7112 | `npm run scan:secrets` | 857 publishable text files inspected; no finding | PASS |
| TC-7112 | `npm run scan:dependencies` | npm/API/Worker scans found no blocking vulnerability | PASS |
| TC-7112 | `npm run validate` | Architecture and development-record validation passed | PASS |
| TC-7112 | `git diff --check` | No whitespace error | PASS |

## Failures and Corrections

- Sandboxed Python could not access the user-scoped `uv` cache; approved external tool access was
  used for project Python gates.
- The first Worker lint pass found only one import-order issue in the new PostgreSQL test; imports
  were ordered and the focused test suite remained green.
- The first static contract run expected an obsolete route-key separator and then an implementation
  type name rather than the port call. Both assertions were corrected to inspect the frozen
  behavior rather than incidental spelling.
- Senior review found a non-contractual `status` field in the internal accepted result, a
  Parser-specific exception in the shared guard, and broad Project UPDATE privilege. All three
  were corrected before final verification.
- The first privilege probe ran against a database where the earlier development form of Migration
  0026 had already granted broad Project UPDATE. The final upgrade now explicitly revokes broad
  UPDATE before granting the one required column; downgrade/upgrade and the probe are rerun below.

## Deferred Verification

- Public endpoint behavior, Hosted task activation and real Provider quality are not claimed.
- Customer-content execution and paid-call post-response recovery are prohibited/deferred.
- Entitlement/quota and automatic Queue retry remain outside 0071.

## Final Status

**Final status:** PASS
