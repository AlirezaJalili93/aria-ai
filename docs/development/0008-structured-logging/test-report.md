# Test Report: 0008 Structured Logging & Correlation

- Increment ID: `0008-structured-logging`
- Date: 2026-08-18
- [Development record](./development.md)

## Environment

- Local OS: Windows
- Branch: `agent/staging-runtime`
- Python: 3.12 repository pin
- uv: 0.12.5
- API: FastAPI 0.141.1
- Shared package: `aria-observability` 0.1.0, local locked path dependency
- Secret values: synthetic values only; never recorded in this report

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-0801 | API/Integration | Request without trace headers | API generates UUID request/correlation IDs, returns them, and logs one JSON completion event |
| TC-0802 | API/Security | Safe and malformed client trace headers | Safe UUIDs are preserved; malformed identifiers are replaced and never echoed |
| TC-0803 | API/Contract | Build a job trace context inside a correlated request | Job receives the same correlation ID with versioned task/account/project metadata |
| TC-0804 | Worker/Contract | Consume job metadata and create provider context | Worker and provider boundary preserve correlation and job IDs without regeneration |
| TC-0805 | Runtime | Start Worker | One structured `worker.runtime_started` event replaces `print()` and reports truthful state |
| TC-0806 | Security | Attempt to log Authorization, query/path values, raw content, prompt, and share token | No sensitive value appears; unmatched paths use a constant marker |
| TC-0807 | Quality | Lint/type-check/build API, Worker, and shared package | All implemented Python is formatted, typed, and compilable |
| TC-0808 | Architecture/CI | Validate versioned job schema and repository architecture | Additional/raw payload fields are forbidden; architecture gates pass |
| TC-0809 | Regression | Run repository test and validation suites | Existing Web/API/Worker/CI behavior remains green |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0801 | `npm run test:api` | Generated UUID headers and exact JSON base-field contract passed | PASS |
| TC-0802 | `npm run test:api` | Safe UUID preservation and malformed-value replacement passed | PASS |
| TC-0803 | `npm run test:api` | Request correlation reached the versioned job context unchanged | PASS |
| TC-0804 | `npm run test:worker`; `npm run test:ci` | Worker/provider context preserved IDs; schema contract rejected extra/raw fields | PASS |
| TC-0805 | `npm run test:worker` | Worker startup emitted JSON with `queue_adapter_configured=false`; no `print()` contract remains | PASS |
| TC-0806 | API/Worker negative tests | Authorization, query/path content, project brief, prompt, and share token values were absent | PASS |
| TC-0807 | `npm run lint`; `npm run typecheck`; `npm run build` | Web, API, Worker, and shared package lint/type-check/build gates passed | PASS |
| TC-0808 | `npm run test:ci`; `npm run validate` | 14 CI/contract tests passed; every A04 architecture check passed. The repository validator remains globally non-zero only for the pre-existing truthful `0007-staging-runtime` hosted-evidence status | PASS |
| TC-0809 | `npm test`; `npm run scan:dependencies`; `npm run scan:secrets` | Web 4, API 28, Worker 14, CI/contract 14, and record-suite 6 tests passed; external dependency audit found no blocker; 124 publishable files had zero secret findings | PASS |

## Failures and Corrections

1. Initial test execution could not locate the sandboxed workspace `uv` binary. The existing pinned workspace executable was resolved and used without changing dependency versions.
2. The first Worker regression run failed because its legacy test expected human-readable `print()` output. The runtime and test now use the canonical structured JSON event.
3. Ruff found three import-order issues and MyPy rejected the new internal package without a typed-package marker. Imports were corrected and `py.typed` was added.
4. Senior review found that unmatched request paths could enter the route field. The fallback was replaced with the constant `/<unmatched>` and a negative leakage test was added.
5. Senior review found the shared package was outside the repository's existing lint/type-check commands. The quality scripts now include it explicitly.
6. The first dependency audit rejected the local path package because it has no registry hash. `uv export --no-emit-local` now excludes internal source while preserving the locked external dependency graph; a CI contract test protects this behavior and the real audit passes.

## Final Status

**Final status:** PASS
