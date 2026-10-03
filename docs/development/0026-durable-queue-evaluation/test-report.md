# Test Report: Durable Queue Candidate Evaluation

- Increment ID: `0026-durable-queue-evaluation`
- Date: 2026-09-05
- [Development record](./development.md)

## Environment

- Windows owner host with Docker Desktop 29.5.2, Compose 5.1.3 and WSL2 Linux engine.
- Dedicated local Redis container only; no hosted or Production Queue.
- Candidate: Celery 5.6.3, isolated from `apps/worker`.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2601 | Integration | Publish while worker is absent, then start worker | One outcome completes after worker starts |
| TC-2602 | Recovery | Kill worker during execution and restart after visibility expiry | Task is redelivered and one outcome completes |
| TC-2603 | Idempotency probe | Publish the same business probe twice | Multiple attempts, one committed probe outcome |
| TC-2604 | Measurement | Measure Redis commands during an idle worker window | Delta is emitted as evidence, not a product limit |
| TC-2605 | Contract | Inspect candidate ack/visibility/serializer configuration | Explicit late ack, loss rejection, prefetch one and JSON only |
| TC-2606 | Architecture | Verify isolation from runtime Worker | No Queue framework enters `apps/worker` and no ADR is accepted |
| TC-2607 | Regression | Run repository tests and architecture validation | All required gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2601 | Publish `worker-absent`, verify zero attempts, start Worker, wait | `attempts=1`, `finished=true`, `outcomes=1` | PASS |
| TC-2602 | Publish 20-second probe, confirm start, kill Worker, wait past experiment visibility, restart | Redelivered with `attempts=2`, `finished=true`, `outcomes=1` | PASS |
| TC-2603 | Publish `duplicate-delivery` twice | `attempts=2`, `outcomes=1` | PASS |
| TC-2604 | Compare Redis `total_commands_processed` across ten idle seconds | `975 → 1011`; measured delta `36` | PASS |
| TC-2605 | Contract test, Python compile/Ruff, and Compose config validation | 4/4 contract tests, syntax/lint and Compose config passed | PASS |
| TC-2606 | Contract readback of `apps/worker`, candidate plan and Compose isolation | Runtime Worker remained Queue-neutral; no hosted identifier or accepted selection | PASS |
| TC-2607 | `npm test` and `npm run validate` | Records 6, contracts 67, Web 18, API 143 passed/33 skipped, Worker 16; validation 22/22 | PASS |

## Failures and Corrections

The Codex sandbox invocation could not load the owner account's Docker CLI plugin configuration and
parsed Compose flags as root Docker flags (`unknown flag: --volumes`). The run stopped before any
evaluation container or volume was changed. This is an execution-identity limitation already
documented in the evaluation plan; the black-box run must use the authenticated owner PowerShell.

The first owner-account run stopped before Docker access because Windows PowerShell's .NET runtime
does not provide the static `RandomNumberGenerator.GetBytes(int)` helper. The runner was corrected to
use `RandomNumberGenerator.Create()`, fill a fixed byte array, and dispose the generator. A contract
test now prevents reintroducing the incompatible static call.

The next owner-account run built the candidate image and reached the first publish, but Compose
replaced the image `CMD` with `publish`, which the OCI runtime treated as an executable. The `probe`
service now has a fixed `python -m queue_eval.cli` entrypoint so Compose run arguments are passed as
CLI subcommands. A contract assertion protects this invocation boundary.

## Final Status

**Final status:** PASS
