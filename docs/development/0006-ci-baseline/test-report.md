# Test Report: 0006 CI Baseline

- Increment ID: `0006-ci-baseline`
- Date: 2026-08-17
- [Development record](./development.md)

## Environment

- OS: Windows (local verification), GitHub-hosted Ubuntu runner (hosted verification)
- Repository: `AlirezaJalili93/aria-ai`
- Default branch: `main`
- Node.js: `24.11.1`
- Python: `3.12.13`
- uv: `0.12.5`
- pip-audit: `2.10.1`
- Secret values: none used or recorded

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-0601 | Contract | CI triggers, named jobs, immutable Actions, commands, and caches | PR/main triggers and documented quality/security gates are present; every Action uses a full SHA |
| TC-0602 | Unit/Security | Empty placeholders plus representative secret/token/URL inputs | Empty values pass; unsafe values produce path/line/detector findings without revealing matches |
| TC-0603 | Integration/Security | Audit npm and independent API/worker lockfile exports | All three audits run and no blocking vulnerability is present |
| TC-0604 | Integration | Lint, type-check, all tests, and all builds | Every repository quality stage passes |
| TC-0605 | Contract | Failure evidence and cache configuration | npm/uv caches are enabled and both reports upload with `if: always()` |
| TC-0606 | Contract | Pull-request template and CODEOWNERS | Required evidence headings and risk-owner paths are present |
| TC-0607 | External/Integration | Repository visibility and `main` branch protection | Repository is public; PR, strict green checks, administrator enforcement, linear history, and code-owner review are enabled; force-push/delete are disabled |
| TC-0608 | Architecture | Development evidence and CI fitness validation | Records link and pass; runtime/action pins, triggers, scans, caches, and artifacts validate |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0601 | `npm run test:ci` | CI contract tests passed; triggers, two jobs, exact refs, commands, and caches verified | PASS |
| TC-0602 | `npm run test:ci` and `npm run scan:secrets` | 3 scanner tests passed; repository scan found zero potential secrets | PASS |
| TC-0603 | `npm run scan:dependencies` | npm: 0/428 vulnerabilities; API and worker: no known vulnerabilities | PASS |
| TC-0604 | `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` | All linters/types passed; 20 tests passed; Web/API/Worker builds passed | PASS |
| TC-0605 | `scripts/test/ci-config.test.js` | Both cache families and two always-uploaded artifacts verified | PASS |
| TC-0606 | `scripts/test/ci-config.test.js` | Required PR headings and CODEOWNERS paths verified | PASS |
| TC-0607 | GitHub API update and readback | `PUBLIC`; strict contexts `Quality` and `Security baseline`; admins/code owners/linear history enforced; force-push/delete disabled | PASS |
| TC-0608 | `npm run validate` and final `npm run quality` | Architecture/documentation checks and the complete local gate passed | PASS |

## Failures and Corrections

1. The first secret-scanner test expected a duplicate environment finding. The expectation was corrected to the detector's documented one-finding-per-line behavior.
2. The repository-wide scanner detected a credential-shaped URL literal inside its own test. The test now assembles representative material at runtime and the publishable scan passes without weakening detection.
3. Node could not spawn `npm.cmd` directly on Windows and initial logs hid the process error. npm invocation is now platform-aware and spawn errors are retained in the report.
4. GitHub rejected Branch Protection and Rulesets for the private repository with `HTTP 403`. The user explicitly authorized public visibility; the repository was made public and protection then applied successfully.

## Final Status

**Final status:** PASS
