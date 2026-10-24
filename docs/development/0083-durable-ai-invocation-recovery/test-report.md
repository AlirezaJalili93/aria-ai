# Test Report: 0083 Durable AI Invocation Recovery

- Increment ID: `0083-durable-ai-invocation-recovery`
- Date: 2026-09-30
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Isolated Docker PostgreSQL 16 for the controlled 0083 gate

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-8301 | REQ-8301 | Stable Attempt validates exact identity and starts durably | PASS |
| TC-8302 | REQ-8302/8303/8305 | One successful invocation produces one Usage/checkpoint; recovery reuses; cleanup follows Job success | PASS |
| TC-8303 | REQ-8302 | Forced checkpoint write failure rolls back both Usage and payload | PASS |
| TC-8304 | REQ-8304 | Started/no-result becomes action-required failure with no fabricated Usage | PASS |
| TC-8305 | REQ-8306 | Cross-Tenant target, DELETE, identity mutation and invalid transition fail | PASS |
| TC-8306 | REQ-8306/8308 | Static contract proves no Hosted composition or content-bearing telemetry/queue surface | PASS |
| TC-8307 | REQ-8307 | Fresh migration, evidence-preserving downgrade refusal and clean downgrade/re-upgrade pass | PASS |
| TC-8308 | Repository gates | Lint, strict typecheck, all tests, build and architecture validation | PASS |

## Commands and Results

```text
npm run lint:worker
PASS

npm run typecheck:worker
PASS — 71 source files

pytest apps/worker/tests/test_ai_invocation_recovery.py
PASS — 4 passed

node --test scripts/test/ai-invocation-recovery-contract.test.js
PASS — 2 passed

npm run test:ai-invocation-recovery-e2e
PASS — 4 PostgreSQL tests; migration downgrade/re-upgrade; CONTROLLED_0083_GATE=PASS

npm test
PASS — CI 194; Eval 35; Web 40; API 456 passed/155 skipped; Worker 167 passed/29 skipped

npm run lint && npm run typecheck && npm run build
PASS

npm run validate
PASS — 23 architecture/documentation checks

npm run scan:secrets
PASS
```

## Execution Results

- Fresh migration reached `0031_ai_invocation_checkpoints` on isolated PostgreSQL 16.
- Four real PostgreSQL recovery/security cases passed under the actual `aria_worker` role.
- Data-bearing downgrade refusal and empty-table downgrade/re-upgrade both passed.
- Repository test, lint, typecheck and production-build suites passed.
- The ordinary API/Worker suites retain their documented PostgreSQL-dependent skips; the dedicated
  0083 PostgreSQL gate is not skipped and passed independently.

## Security and Leakage Evidence

- The checkpoint table uses forced RLS and Account-scoped Worker transactions.
- Worker DELETE is denied; identity/transition mutations are rejected by PostgreSQL.
- Normalized result exists only in `result_ready` and becomes NULL after Job success cleanup.
- Static and code review show no prompt, raw response or normalized result in logs, metrics,
  Outbox or Queue messages.
- No real Provider credential, customer content or paid invocation was used.

## Final Status

**Final status:** PASS

The synthetic recovery foundation, Migration 0031 and all required repository gates pass.
Real Provider/customer-content composition and Hosted activation remain explicitly outside 0083.
