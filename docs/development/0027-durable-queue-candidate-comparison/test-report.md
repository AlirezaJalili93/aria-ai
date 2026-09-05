# Test Report: Durable Queue Candidate Comparison

- Increment ID: `0027-durable-queue-candidate-comparison`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

- Static checks: Windows repository worktree with Node and Python 3.12 toolchains.
- Constrained-run cache: `UV_CACHE_DIR=.uv-cache-codex`, because the sandbox cannot write the
  owner-level global uv cache.
- Integration target: authenticated owner PowerShell, Docker Desktop Linux/WSL2 and two dedicated
  local Redis Compose projects.
- Candidates: Dramatiq 2.2.1 and RQ 2.12.0, isolated from `apps/worker`.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2701 | Contract | Inspect exact candidate and lock versions | Dramatiq 2.2.1 and RQ 2.12.0 are exact and isolated |
| TC-2702 | Integration | Publish while each Worker is absent, then start it | One outcome completes after Worker startup |
| TC-2703 | Recovery | Kill each Worker during execution and restart | Native candidate recovery redelivers; one outcome remains |
| TC-2704 | Security/idempotency | Inspect serializers and publish duplicate business probes | JSON-only candidate boundary and one committed outcome |
| TC-2705 | Retry/scheduling | Trigger native retry and delayed delivery | Retry/delay behavior completes without custom recovery |
| TC-2706 | Measurement | Measure commands during ten idle seconds | Candidate-specific command delta is emitted as evidence |
| TC-2707 | Architecture/regression | Inspect runtime isolation and validator; run required gates | Runtime stays unchanged; validator permits only the accepted Worker pin and all gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2701 | Contract test, lock inspection, module import, Ruff/compile and Compose config | 6/6 candidate contract tests passed; exact imports, lint/compile and both configs passed | PASS |
| TC-2702 | Run both candidate PowerShell harnesses | Both worker-absent probes stayed at zero before startup and completed with one outcome after startup | PASS |
| TC-2703 | Force-kill/restart within both harnesses | Dramatiq and RQ each recovered with `attempts=2`, `finished=true`, `outcomes=1` | PASS |
| TC-2704 | Contract test plus duplicate probes | Explicit JSON boundaries passed; each candidate recorded two attempts and one outcome | PASS |
| TC-2705 | RQ exception retry and both delayed-delivery probes | RQ retry=`attempts=2/outcomes=1`; delayed probes remained exactly zero before due time, then completed | PASS |
| TC-2706 | Compare ten-second Redis command deltas | Dramatiq=`141`; RQ=`249`; Celery baseline from 0026=`36` | PASS |
| TC-2707 | `npm test` and `npm run validate` | Records 6, contracts 73, Web 18, API 143 passed/33 skipped, Worker 16; validation 22/22; accepted Celery pin/API isolation guard passed | PASS |

## Failures and Corrections

Senior review found that the original zero-attempt precondition expressed only a lower bound and
could therefore false-pass after early execution started. Both CLIs and runners were corrected to
require `max_attempts=0`; the contract test now protects this boundary.

The first RQ Docker run passed worker absence and ordinary exception retry but timed out waiting for
forced-loss redelivery (`attempts=1`, `outcomes=0`). Worker logs showed registry maintenance only at
startup. Source inspection confirmed the default idle dequeue block can outlast the bounded test.
The isolated Worker now uses a 16-second fixture TTL, which yields a one-second idle dequeue block;
the real approximately 61-second abandoned-job lease remains unchanged. The clean rerun recovered
the Job with two attempts and one committed outcome.

After ADR acceptance, the first full regression rerun reached the API step but stopped before test
collection because the owner-level uv cache returned Windows `Access denied`. Re-running the same
suite with the cache redirected inside the worktree passed. No application assertion failed in that
environmental attempt.

## Final Status

**Final status:** PASS
