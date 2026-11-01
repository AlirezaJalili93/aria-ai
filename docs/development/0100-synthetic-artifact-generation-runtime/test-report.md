# Test Report: 0100 Synthetic Artifact Generation Worker Runtime

- Increment: `0100-synthetic-artifact-generation-runtime`
- Date: 2026-10-12
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Node.js/npm constrained by the repository
- Python 3.12 through repository `uv` runners
- Isolated PostgreSQL 16 test container on `127.0.0.1:55434`
- Runtime principal: actual `aria_worker` database role
- Synthetic fixtures only; no Provider, customer content or hosted runtime

## Commands

```powershell
npm run test:artifact-generation-runtime
node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests/test_artifact_foundation_domain.py apps/api/tests/test_artifact_foundation_service.py apps/api/tests/test_artifact_foundation_postgres.py
node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests/test_artifact_generation_runtime.py apps/worker/tests/test_artifact_generation_runtime_postgres.py
npm run lint
npm run typecheck
npm test
npm run build
npm run validate
git diff --check
```

## Test Cases

| ID | Expected | Actual | Status |
|---|---|---|---|
| TC-1001 | Identifier-only envelope and disabled retry | Extra vocabulary rejected; task mapping exact | PASS |
| TC-1002 | Fixed no-shell CLI renders canonical synthetic AST only | Fixed builder boundary exercised | PASS |
| TC-1003 | Canonical Manifest/checkpoint identity is deterministic | Repeated canonicalization matched | PASS |
| TC-1004 | Create-or-verify publication writes Manifest last | Matching replay accepted; mismatch rejected | PASS |
| TC-1005 | Checkpoint recovery does not rerun Renderer | Same identities finalized with one builder call | PASS |
| TC-1006 | Mismatched Job/Event and wrong event fail closed | PostgreSQL helpers rejected both | PASS |
| TC-1007 | Cross-project ArtifactVersion and cross-Tenant Scope fail closed | Constraints/helper rejected both without identifier leakage | PASS |
| TC-1008 | Duplicate delivery after success is a no-op | No duplicate effect | PASS |
| TC-1009 | Concurrent Workers have one owner; unowned finalize denied | Real-role tests passed | PASS |
| TC-1010 | Worker cannot mutate protected tables directly | Direct ArtifactVersion mutation denied | PASS |
| TC-1011 | No Scope, AST, object or storage-content leakage | Bounded-error assertions passed | PASS |
| TC-1012 | Fresh migration, downgrade/re-upgrade and focused suites pass | Migration chain and 20 focused Python tests passed | PASS |
| TC-1013 | Repository quality gates pass | Lint, typecheck, full tests and build passed; final validation recorded below | PASS |

## Execution Results

- 0100 Node Contract: PASS, 3 tests.
- Focused API Domain/service/PostgreSQL: PASS, 13 tests.
- Focused Worker unit/PostgreSQL: PASS, 7 tests.
- Fresh migration through 0039: PASS.
- Downgrade 0039 → 0038 and re-upgrade: PASS on the isolated test database.
- `npm run lint`: PASS.
- `npm run typecheck`: PASS (203 API and 87 Worker source files).
- `npm run build`: PASS for Renderer, Web, API and Worker.
- First `npm test` run: API PASS (`739 passed, 1 skipped`); Worker exposed three cleanup-fixture
  regressions because the new claim FK requires its child table to be truncated with Outbox.
- After the scoped fixture correction, affected Worker rerun: PASS, 11 tests.
- Final `npm test`: PASS; API `739 passed, 1 skipped`, Worker `249 passed, 2 skipped`, and every
  Node/Renderer/Web Contract suite passed.
- Environment-gated skipped tests are not represented as PASS by this report.
- `npm run validate`: PASS after the final documentation sync.
- `git diff --check`: PASS after the final documentation sync.
- Results prove Synthetic Option 1 only. They do not prove isolation after compromise of the shared
  Worker credential; `WORKER-CROSS-TENANT-001` remains OPEN.

## Final Status

**Final status:** PASS
