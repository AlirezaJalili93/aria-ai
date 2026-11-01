# Test Report: 0039 Context Structuring Workflow

- Increment ID: `0039-context-structuring-workflow`
- Date: 2026-09-06
- [Development record](./development.md)

## Environment

- Windows workspace, PowerShell
- Node/npm repository toolchain
- Python 3.12 API and Worker environments managed through `uv`
- Local PostgreSQL 16 Docker service when integration tests run
- Fake AI execution and unsupported-claim adapters; no external Provider

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3901 | Application | Fake AI execution returns a valid complete candidate Batch | Full Batch persisted through shared use case |
| TC-3902 | Repository | Deleted Sources and non-ready Versions exist | Snapshot excludes both |
| TC-3903 | Repository/Application | Multiple ready Versions and a Source added during AI execution | Latest ready selected once; later Source excluded |
| TC-3904 | Application | AI response does not match the candidate schema | Whole Batch rejected; zero writes |
| TC-3905 | Application | Fact has no valid Source Reference | Whole Batch rejected; zero writes |
| TC-3906 | Application | Source Reference is absent/mismatched/out of bounds | Whole Batch rejected; zero writes |
| TC-3907 | Application | Unsupported-claim validator rejects a candidate | Whole Batch rejected; zero writes |
| TC-3908 | Application | Two candidates have exactly equal `(item_type, content)` | Stable `DUPLICATE_CONTEXT_ITEM`; zero writes |
| TC-3909 | Application/PostgreSQL | Persistence/commit fails | Rollback; Project version unchanged and unconsumed |
| TC-3910 | PostgreSQL concurrency | Two executions allocate a Context Version concurrently | Unique gap-free versions and atomic Project advancement |
| TC-3911 | Worker architecture | Worker wrapper executes the shared Backend Application use case | No duplicate Context Domain or validation implementation |
| TC-3912 | Logging | Success/failure events inspect emitted fields | Lifecycle metadata only; no content, refs or rationale |
| TC-3913 | Contract | Inspect imports and public surfaces | No Provider SDK, Endpoint, Queue wiring, Job type, Repair or fallback |
| TC-3914 | Regression | Run repository quality gates | Tests, lint, types, builds and validators pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-3901, TC-3904–TC-3908, TC-3912 | Application suite with Fake AI/claim/ledger/repository adapters | 11 passed | PASS |
| TC-3902, TC-3903, TC-3909, TC-3910 | Real PostgreSQL snapshot, concurrency and rollback suite | 3 passed | PASS |
| TC-3911 | Worker delegation plus AI/Usage compatibility regression | 13 focused tests passed | PASS |
| TC-3913 | H02/AI/Usage architecture contract suite | 8 focused tests passed | PASS |
| TC-3914 | `npm run test:ci` | 105 passed | PASS |
| TC-3914 | `npm run test:web` | 18 passed | PASS |
| TC-3914 | `npm run test:api` with real `TEST_DATABASE_URL` | 240 passed | PASS |
| TC-3914 | `npm run test:worker` | 55 passed | PASS |
| TC-3914 | `npm run lint; npm run typecheck; npm run build` | All Web/API/Worker/shared-package commands passed | PASS |
| TC-3914 | Final `npm test` and `npm run validate` | All suites and architecture/development-record gates passed | PASS |
| TC-3914 | `git diff --check` | No whitespace errors | PASS |

## Failures and Corrections

The Red contract test first failed because the shared H02 package and Worker wrapper did not exist.
The initial Python Red commands also exposed the sandbox-denied global `uv` cache, so subsequent
runs used the repository-local `.tools/uv-cache` without weakening a test. PostgreSQL verification
first failed because the already-approved local Docker services were stopped; after restarting the
same Compose stack, the focused database suite passed. Senior review then added a real transaction
failure test to prove flushed items and Version advancement roll back together. Pytest continued to
report the existing non-failing cache-permission warning and the upstream TestClient deprecation.

## Final Status

**Final status:** PASS
