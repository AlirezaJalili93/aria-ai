# Test Report: 0049 — Gap Detection Foundation

- **Status:** PASS (S1-J02-A)
- **Increment:** S1-J02-A
- **Date:** 2026-09-09
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12-compatible API runtime
- PostgreSQL 16 local Docker service for final integration evidence

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-4901 | Unit/Integration | Context and Requirement membership/revision changes | `GAP_SNAPSHOT_CHANGED`; zero business writes |
| TC-4902 | Contract/Unit | Candidate fields and resolution vocabulary | Only the approved schema/vocabulary is accepted |
| TC-4903 | Unit/Integration | Source provenance and affected Requirement boundaries | Out-of-snapshot/cross-tenant references are rejected |
| TC-4904 | Unit | Exact canonical duplicate candidates | Entire Batch rejected; no silent merge or fuzzy matching |
| TC-4905 | Integration | Gaps, links and Job result persistence | All commit together or all roll back |
| TC-4906 | Unit/Integration | Non-empty, empty and failed terminal replay | No AI call, Usage append or write on replay |
| TC-4907 | Unit | Initial/repair provider calls | One append-only Usage Record per invocation |
| TC-4908 | Unit/Contract | AI proposes Critical before J02-B | Severity may persist, but no authoritative Critical result without evaluator match |
| TC-4909 | Unit/Contract | Detection telemetry | Required safe events emit; prohibited content never logs |
| TC-4910 | Regression | Repository quality gates | All mandated checks pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
| --- | --- | --- | --- |
| TC-4901 | `pytest ...test_gap_detection_application.py ...test_gap_detection_postgres.py` | Dual Context/Requirement snapshot drift and concurrent delivery behavior passed | PASS |
| TC-4902 | Focused pytest + `node --test scripts/test/gap-detection-contract.test.js` | Candidate fields, six resolution values and DB rejection of unapproved values passed | PASS |
| TC-4903 | Focused PostgreSQL suite | Invalid persisted provenance, out-of-snapshot affected IDs and tenant boundaries rejected | PASS |
| TC-4904 | Focused Application suite | Canonically reordered exact duplicate rejected atomically; bounded repair path metered | PASS |
| TC-4905 | Focused PostgreSQL suite | Gap/link/Job result atomicity, restrictive FKs, RLS and rollback passed | PASS |
| TC-4906 | Focused + full API suites | Non-empty/empty terminal replay bypassed AI, Usage and writes; corrupt metadata failed closed | PASS |
| TC-4907 | Focused Application/PostgreSQL suites | One Usage record per provider invocation including repair | PASS |
| TC-4908 | Focused Application + contract suites | Critical candidate remained non-authoritative without deterministic evaluator match | PASS |
| TC-4909 | `pytest ...test_observability.py` + contract suite | Safe counts/versions emitted; prohibited content discarded | PASS |
| TC-4910 | Commands below | All repository quality gates passed | PASS |

### Final commands

| Command | Result |
| --- | --- |
| `npm run test:ci` | 130/130 PASS |
| `npm run test:eval` | 24/24 PASS |
| `npm run test:web` | 26/26 PASS |
| `TEST_DATABASE_URL=... pytest -q apps/api/tests` | 392/392 PASS; one pre-existing Starlette/httpx deprecation warning |
| `npm run test:worker` | 57/57 PASS |
| `npm run lint` | PASS |
| `npm run typecheck` | PASS; API 116 and Worker 26 source files checked |
| `npm run build` | PASS; Next.js production build plus API/Worker compileall |
| `npm test` with PostgreSQL integration enabled | PASS: records 6, CI 130, Eval 24, Web 26, API 392, Worker 57 |
| `npm run validate` | PASS in final gate run |
| `npm run scan:secrets` | PASS in final gate run |
| `git diff --check` | PASS in final gate run |

## Failures and Corrections

- Contract-first run initially failed because `0015_gap_detection.py` and `gap_detection.py` did
  not exist; implementation made the same tests pass.
- The first integration run exposed event-loop reuse in the test harness and one multi-statement
  asyncpg fixture; tests were corrected without weakening assertions.
- Re-editing an unapplied-development Migration left the disposable DB with its earlier constraint
  name. The exact test-only database was verified, dropped, recreated and the final migration was
  applied from zero; production/staging data was untouched.
- Senior review found and fixed duplicate telemetry during successful repair, a concurrent Job
  replay race, and missing ready-provenance revalidation. Regression remained green afterward.

## Final Status

**Final status:** PASS FOR S1-J02-A — full S1-J02 remains NOT DONE pending J02-B.
