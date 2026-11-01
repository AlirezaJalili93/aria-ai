# Test Report: 0099 ArtifactVersion Foundation

- Increment: `0099-artifact-version-foundation`
- Date: 2026-10-11
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12 through repository `uv` runner
- PostgreSQL 18 local throwaway database `aria_0099_test_20261011`
- Node.js 24 / npm 11

## Commands

```powershell
node scripts/run-uv.mjs --directory apps/api run pytest -q tests/test_artifact_foundation_domain.py tests/test_artifact_foundation_service.py
$env:TEST_DATABASE_URL='postgresql+asyncpg://***@127.0.0.1:5432/aria_0099_test_20261011'
node scripts/run-uv.mjs --directory apps/api run pytest -q tests/test_artifact_foundation_postgres.py
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
| TC-9901 | Approved Scope allocates Artifact, Version, Job and Outbox atomically; replay is exact | One row each and replay returned same allocation | PASS |
| TC-9902 | Concurrent initial/revision allocation cannot duplicate Artifact or version number | Initial race produced one winner; concurrent revisions allocated 2 and 3 with the same valid parent | PASS |
| TC-9903 | Non-approved Scope fails before allocation | No ArtifactVersion persisted | PASS |
| TC-9904 | Finalization failure preserves queued/running state; recovery uses same identities | Fault trigger rolled back all finalization effects; recovery and replay used same Job/Version | PASS |
| TC-9905 | Invalid Manifest, non-ready current and cross-tenant references fail closed | Verification/FK/trigger guards rejected each mutation | PASS |
| TC-9906 | Ready history is immutable, non-deletable and public roles lack direct access | Version mutation/delete and Artifact delete rejected; RLS enabled and grants absent | PASS |
| TC-9907 | Domain/Application invariants reject malformed lineage/Manifest and call atomic Port once | Six focused unit tests passed | PASS |
| TC-9908 | Repository regression gates remain green | Lint, typecheck, full tests, build, validate and diff check recorded below | PASS |

## Execution Results

- Focused Domain/Application: PASS, 6 tests.
- Real PostgreSQL migration/repository/recovery: PASS, 7 tests on a freshly migrated database.
- `npm run lint`: PASS.
- `npm run typecheck`: PASS (203 API and 81 Worker source files).
- `npm test`: PASS; API `558 passed, 182 skipped`, Worker `208 passed, 36 skipped`,
  and all Node/Renderer/Web contract suites passed.
- `npm run build`: PASS for Renderer, Web, API and Worker.
- The first full test attempt reached the Worker suite but Windows denied pytest's shared user Temp
  directory (`207 passed, 36 skipped, 1 environmental error`). The complete command was repeated
  with `TEMP/TMP` bound to a disposable Workspace directory and passed without product-code change.
- Environment-gated tests not executed by the repository-wide run are not represented as PASS.
- Non-gating diagnostic `alembic check`: NOT CLEAN because the existing SQLAlchemy metadata omits
  `usage_records`, `provider_price_versions` and `ai_invocation_checkpoints` and reports unrelated
  legacy index/constraint drift. It reported no drift for the new Artifact tables; the fresh 0038
  migration and all real-PostgreSQL 0099 cases passed.

## Final Status

**Final status:** PASS
