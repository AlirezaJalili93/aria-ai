# Test Report: 0040 Context Validation Repair

- Increment ID: `0040-context-validation-repair`
- Date: 2026-09-06
- [Development record](./development.md)

## Environment

- Windows workspace, PowerShell
- Node/npm repository toolchain
- Python 3.12 API and Worker environments managed through `uv`
- Local PostgreSQL 16 Docker service for migration and adapter evidence
- Fake AI execution, claim validator, repository and logger; no external Provider

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-4001 | Application | `max_repairs=0` and initial output fails validation | One AI call; original validation error; no Repair |
| TC-4002 | Application | `max_repairs=1` and initial schema failure | Exactly one Repair call |
| TC-4003 | Application | Schema/provenance/unsupported/duplicate output defect | Repair eligible |
| TC-4004 | Application | Provider execution fails | Repair not triggered |
| TC-4005 | Application | Repository/DB operation fails | Repair not triggered |
| TC-4006 | Application | Ready Source is absent or runtime Source state is invalid | Repair not triggered |
| TC-4007 | Application | `insufficient_context` validation result | Repair not triggered |
| TC-4008 | Contract/Application | Repair invocation inspects workflow, routing, prompt and policy | Same workflow/routing; explicit Repair prompt; no escalation/fallback |
| TC-4009 | Application | Repair output passes all H02 validations | One complete atomic Context Version is persisted |
| TC-4010 | Application | Repair output fails validation | `CONTEXT_REPAIR_EXHAUSTED`, `retryable=false` |
| TC-4011 | Application | Repair is exhausted | No Context Item write or Version increment |
| TC-4012 | Application | Original and Repair calls return | Two independent Usage records with `repair_no=0,1` |
| TC-4013 | Application | Provider reports retries during Repair | `retry_no` changes independently; `repair_no` remains `1` |
| TC-4014 | PostgreSQL | `repair_no` schema accepts non-negative values and rejects negatives | Default/constraint work; no database ceiling of 1 |
| TC-4015 | Logging | Inspect Repair lifecycle event fields | Bounded reason codes only; no Source/Candidate/Prompt content |
| TC-4016 | Regression | Repository quality gates | Tests, lint, types, builds and validators pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-4001–TC-4013, TC-4015 | Focused Application suite with sequential Fake AI and safe logger | 26 passed | PASS |
| TC-4014 | Real PostgreSQL Usage + Context persistence suites | 17 passed | PASS |
| TC-4008, TC-4014, TC-4015 | H03/H02/G05 architecture contract suites | 9 focused tests passed | PASS |
| TC-4016 | `npm run test:ci` after fitness correction | 108 passed | PASS |
| TC-4016 | `npm run test:web` | 18 passed | PASS |
| TC-4016 | `npm run test:api` with real `TEST_DATABASE_URL` | 257 passed | PASS |
| TC-4016 | `npm run test:worker` | 55 passed | PASS |
| TC-4016 | `npm run lint:api; npm run lint:worker` | Ruff passed for both Python surfaces | PASS |
| TC-4016 | `npm run typecheck:api; npm run typecheck:worker` | Mypy passed: 90 API/shared and 23 Worker/shared files | PASS |
| TC-4016 | `npm run build` | Next.js production build and API/Worker compilation passed | PASS |
| TC-4016 | Final `npm test` and `npm run validate` | Repository test and 22-check validation gates passed | PASS |
| TC-4016 | `git diff --check` | No whitespace errors; informational LF/CRLF warnings only | PASS |

## Failures and Corrections

The first contract test failed because Migration 0009 did not exist, proving the test was Red before
implementation. The first Application run then failed at import because the Repair contract types
did not exist. After implementation, five historical H02 failure tests reached the newly enabled
Repair path; those tests were corrected to use the approved explicit disabled policy because their
purpose is to assert original H02 errors. Senior review also found three fitness Regexes that were
sensitive to Markdown line breaks; they were made whitespace/newline tolerant without reducing the
required semantic assertions. Pytest continued to report the existing non-failing cache-permission
warning and the upstream TestClient deprecation.

## Final Status

**Final status:** PASS
