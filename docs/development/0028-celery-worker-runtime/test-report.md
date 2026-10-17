# Test Report: Celery Worker Runtime

- Increment ID: `0028-celery-worker-runtime`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

- Windows repository worktree with Node and Python 3.12 toolchains.
- Celery runtime tests use configuration objects and injected runtime doubles; no hosted Queue is
  contacted and no credential is recorded.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2801 | Contract | Inspect Worker dependency and lock | Celery Redis 5.6.3 is exact and absent from API |
| TC-2802 | Unit/contract | Omit or invalidate Queue runtime values | Startup fails closed; no implicit value is used |
| TC-2803 | Unit/contract | Inspect Celery application configuration | JSON-only, late ack, Worker-loss rejection and prefetch one |
| TC-2804 | Unit/contract | Inspect result configuration | Celery result backend is disabled and results are ignored |
| TC-2805 | Unit/architecture | Run composition root with injected runtime | Adapter is invoked and truthful structured startup is emitted |
| TC-2806 | Contract | Inspect runtime adapter and task tree | No product timeout/retry/dead policy or business handler is added |
| TC-2807 | Regression | Run repository quality gates | Existing architecture and behavior remain green |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2801 | Node contract test; `uv lock --project apps/worker` | Worker lock contains Celery 5.6.3 with Redis extra; API remains free of Queue frameworks | PASS |
| TC-2802 | Worker unit tests for missing/invalid settings | Missing runtime configuration fails closed; positive values and non-empty Queue name are enforced | PASS |
| TC-2803 | Celery adapter unit/contract tests | JSON-only, late ack, Worker-loss rejection, prefetch one and explicit visibility pass | PASS |
| TC-2804 | Celery adapter unit test | `result_backend=None` and `task_ignore_result=True` pass; PostgreSQL remains canonical | PASS |
| TC-2805 | Worker unit tests with injected runtime probe | Startup emits `queue_adapter_configured=true` and invokes the runtime exactly once | PASS |
| TC-2806 | Node contract test and source review | No product timeout, retry/backoff, exhausted policy or business task wrapper was added | PASS |
| TC-2807 | `npm test`; `npm run lint`; `npm run typecheck`; `npm run build:worker`; `npm run validate`; `git diff --check` | Records 6; contracts 78; Web 18; API 143 passed/33 skipped; Worker 22; lint/typecheck/build/validation 22/22; diff clean | PASS |

## Failures and Corrections

- The first contract run had an invalid JavaScript template-literal escape; the assertion was
  corrected and all five contract tests passed.
- Strict mypy rejected Celery because the third-party package has no type marker; the single
  Infrastructure import is explicitly isolated with the narrow `import-untyped` suppression.
- The first Worker test extension mixed secret-leak assertions with integer validation; those cases
  were separated and now pass without weakening secret checks.
- Docker image smoke was not executed after the adapter change because the escalated build approval
  was unavailable. No hosted or production Queue was contacted.

## Final Status

**Final status:** PASS
