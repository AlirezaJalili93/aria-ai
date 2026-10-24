# Test Report: 0084 AI-01 Durable Checkpoint Integration

- Increment ID: `0084-ai01-durable-checkpoint-integration`
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
| TC-8401 | REQ-8401/8402 | Exactly one Attempt ID is created before invocation and returned by the Fake | PASS |
| TC-8402 | REQ-8403/8404 | Fingerprint is order-stable; codec strictly round-trips only approved fields | PASS |
| TC-8403 | REQ-8407 | Wrong codec/shape/order/identity/hash fails closed | PASS |
| TC-8404 | REQ-8402/8405/8406 | Failed Domain commit retains `result_ready`; recovery invokes Provider zero additional times and finalizes atomically | PASS |
| TC-8405 | REQ-8403/8404/8407 | Source identity/hash mismatch and tampered payload are rejected | PASS |
| TC-8406 | REQ-8401/8409 | Static contract proves single-attempt ownership and no Hosted composition | PASS |
| TC-8407 | REQ-8408 | Worker cross-Tenant checkpoint target is denied; Migration 0032 downgrade/re-upgrade passes | PASS |
| TC-8408 | Repository gates | Full tests, lint, typecheck, build, validation and secret scan | PASS |

## Commands and Results

```text
pytest test_context_structuring_checkpoint.py + consumer regressions
PASS — 12 passed

npm run lint:worker
PASS

npm run typecheck:worker
PASS — 73 source files

pytest apps/api/tests/test_context_structuring_application.py
PASS — 28 passed

npm run lint:api && npm run typecheck:api
PASS — API typecheck 166 source files

npm run test:ai01-checkpoint-integration-e2e
PASS — 8 tests; fresh Migration to 0032; downgrade/re-upgrade;
CONTROLLED_0084_GATE=PASS

npm test
PASS — CI 194; Eval 35; Web 40; API 456 passed/155 skipped;
Worker 173 passed/30 skipped

npm run lint && npm run typecheck && npm run build
PASS — API 166 and Worker 73 typed source files

npm run validate
PASS — 23 architecture/documentation checks after report finalization

npm run scan:secrets
PASS — 977 publishable text files inspected
```

## Execution Results

- Crash was injected after `result_ready` and before the Domain commit.
- The failed transaction exposed no Context Item, Project version or Job success.
- Recovery reused the same Job and Attempt; Provider invocation and Usage counts remained one.
- Final transaction produced one Context Version, succeeded the Job, finalized the checkpoint,
  cleared normalized content and retained its hash.
- Codec/fingerprint tampering and Worker cross-Tenant access were rejected.

## Security and Leakage Evidence

- The test runs the recovery path under `aria_worker`, not the database owner.
- The checkpoint remains Account/Project/Job scoped under forced RLS.
- Source text, normalized result, generated content and Queue payload are absent from logs.
- No real Provider, customer content, credential or paid invocation is used.

## Final Status

**Final status:** PASS

The focused PostgreSQL gate and every required repository-wide gate pass. Real Provider,
customer-content, paid, Hosted and multi-attempt checkpoint activation remain outside 0084.
