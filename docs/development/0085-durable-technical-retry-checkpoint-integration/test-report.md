# Test Report: 0085 Durable Technical-Retry Checkpoint Integration

- Increment ID: `0085-durable-technical-retry-checkpoint-integration`
- Date: 2026-09-30
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Isolated Docker PostgreSQL 16
- PostgreSQL runtime principal: `aria_worker`

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-8501 | REQ-8501/8505 | Static contract permits only timeout and two Primary attempts | PASS |
| TC-8502 | REQ-8502/8503/8505/8506 | Timeout then success produces two distinct Attempts and exactly two Usage rows | PASS |
| TC-8503 | REQ-8503/8504/8507 | Crash after `failed_known` reuses persisted schedule/fingerprint and never repeats Attempt 0 | PASS |
| TC-8504 | REQ-8502 | Attempt 0 Usage is failed/unavailable with NULL tokens/cost; Attempt 1 Usage is complete | PASS |
| TC-8505 | REQ-8504 | Concurrent logical retry insertion resolves to exactly one Attempt 1 | PASS |
| TC-8506 | REQ-8501/8507 | Ambiguous `started`, tampered input and cross-Tenant targets fail closed | PASS |
| TC-8507 | REQ-8506 | Checkpoint/Usage atomic rollback and migration downgrade/re-upgrade pass | PASS |
| TC-8508 | REQ-8507 | Full tests, lint, typecheck, build, validation and secret scan | PASS |

## Commands and Results

```text
pytest focused checkpoint units
PASS — 17 passed

npm run test:durable-technical-retry-contract
PASS — 2 passed

npm run test:durable-technical-retry-e2e
PASS — 13 tests; fresh Migration to 0033; downgrade/re-upgrade;
CONTROLLED_0085_GATE=PASS

npm run test:ci / test:eval / test:web / test:api / test:worker
PASS — 194 / 35 / 40 / 456 passed + 155 skipped / 174 passed + 34 skipped

npm run lint / npm run typecheck / npm run build
PASS

npm run scan:secrets
PASS — 983 publishable text files inspected

npm test / npm run validate
PASS — final repository gates
```

## Execution Results

- Attempt 0 timed out once, persisted `failed_known`, unavailable Usage and one retry timestamp.
- A synthetic crash after that commit left the same Job recoverable and created no Attempt 1.
- Recovery honored the original timestamp, invoked only Attempt 1 and produced one Context Version.
- Both invocations used distinct IDs and produced exactly two Usage rows.
- Concurrent retry-row creation converged on one logical Attempt 1.
- Migration downgrade/re-upgrade passed after controlled fixture cleanup.

## Security and Leakage Evidence

- Runtime paths execute as `aria_worker`, not the database owner.
- Forced RLS rejects cross-Tenant checkpoint targeting.
- Raw Provider errors, Source content, normalized output and customer data are absent from logs.
- No real Provider, paid call, customer content or Hosted activation is used.

## Final Status

**Final status:** PASS

The controlled PostgreSQL gate and all repository-wide required gates passed. API and Worker
skip counts remain environmental/integration-target exclusions and are not represented as passed
tests.
