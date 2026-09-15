# Test Report: 0051 — Clarification Domain and API

- **Increment:** S1-J03-A
- **Date:** 2026-09-12
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Python 3.12 environments managed by repository `uv` runners
- Node.js 24+ / npm 11+
- PostgreSQL 16 Alpine in local Docker Desktop
- Dedicated temporary database: `aria_j03a_test_20260909`
- Fake deterministic AI-04 Provider only; no real Provider or customer data

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-5101 | Domain/DB | Closed status/creator vocabulary and user creator invariant | Invalid values/creator shape rejected |
| TC-5102 | Domain/DB | Two terminal Resolutions target one Clarification | First persists; second is rejected |
| TC-5103 | Domain/API/DB | Answer/action shapes and user/client attribution | Required text and null-only actions enforced; system rejected |
| TC-5104 | Application/PostgreSQL | Resolve one of multiple questions, then the last | Gap stays open until no open question remains |
| TC-5105 | Application/API | Ignore question versus explicit dismiss Gap | Ignore never dismisses; only explicit command sets dismissed |
| TC-5106 | Contract/API | Separate question, edit, Resolution and dismissal routes | OpenAPI and runtime expose only approved commands |
| TC-5107 | Application/API | Same/different idempotency input and stale CAS timestamp | Safe replay; conflicting key/stale write gets stable 409 |
| TC-5108 | Domain/PostgreSQL | Persian-safe normalization and concurrent exact duplicate | ZWNJ preserved; one normalized open question only |
| TC-5109 | PostgreSQL/API | Cross-tenant linkage/access and parent delete | FK/repository rejects linkage; response is safe 404; RESTRICT holds |
| TC-5110 | Contract | Fake generator satisfies provider-neutral AI-04 port | Deterministic candidate; no Provider SDK/name |
| TC-5111 | Security | Structured event payload inspection | IDs/closed metadata only; no question/answer/client content |
| TC-5112 | Quality | Migration round-trip, lint/type/tests/build/docs/secrets | Every mandatory gate passes |

## Execution Results

| ID | Command or steps | Actual result | Status |
| --- | --- | --- | --- |
| TC-5101–TC-5111 | Focused Python J03-A suite | 28/28 PASS, including 4 PostgreSQL cases | PASS |
| TC-5106–TC-5111 | `npm run test:ci` | 140/140 PASS | PASS |
| TC-5112 | `npm run lint` | Web ESLint and API/Worker Ruff PASS | PASS |
| TC-5112 | `npm run typecheck` | Web TypeScript, API 123 files, Worker 27 files PASS | PASS |
| TC-5112 | `npm run test:eval` | 24/24 PASS | PASS |
| TC-5112 | `npm run test:web` | 26/26 PASS | PASS |
| TC-5101–TC-5112 | `TEST_DATABASE_URL=... npm run test:api` | 435/435 PASS | PASS |
| TC-5112 | `npm run test:worker` | 57/57 PASS | PASS |
| TC-5112 | `npm run build` | Next.js, API and Worker production builds PASS | PASS |
| TC-5112 | `TEST_DATABASE_URL=... npm test` | Records 6; CI 140; Eval 24; Web 26; API 435; Worker 57 — all PASS | PASS |
| TC-5112 | `npm run validate` | Final architecture/development-record validation PASS | PASS |
| TC-5111–TC-5112 | `npm run scan:secrets`; `git diff --check` | No secret or whitespace error | PASS |

## Failures and Corrections

- Initial full lint found one import-order defect after moving the text normalizer into the shared
  Application package; import order was corrected and the complete cycle reran cleanly.
- Initial Contract CI found two predecessor tests asserting that OpenAPI must contain no `/gaps`
  path. After J03-A approval that assertion was stale. The tests now still reject unapproved Gap
  detection/create operation IDs while explicitly recognizing the approved Clarification command.
- The runner reports the existing Starlette/httpx deprecation warning and local Pytest cache write
  warning. Both are non-failing and unrelated to J03-A behavior.

## Database Evidence

- Fresh migration chain reached `0016_clarifications`.
- PostgreSQL rejected cross-tenant Clarification/Resolution relationships, duplicate normalized
  open questions, invalid answer shapes and a second Resolution.
- Resolving the first of two questions left the Gap open; resolving the last changed it to resolved
  with `resolved_at` populated.
- Downgrade to `0015_gap_detection` removed only J03-A objects; re-upgrade recreated them.
- The dedicated temporary database is removed after final verification and its absence is checked.

## Final Status

**Final status:** PASS
