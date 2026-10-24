# Test Report: 0079 Provider Timeout Recovery E2E

- Increment ID: `0079-provider-timeout-recovery-e2e`
- Date: 2026-09-28
- [Development record](./development.md)

## Environment

Windows/PowerShell, Python 3.12 virtual environments, dedicated local
PostgreSQL 16, local Redis DB 15, `aria_worker`, synthetic fixture/Fake Provider.
No real Provider credentials, customer content or Hosted runtime.

## Test Cases

| ID | Type | Scenario | Expected result |
| --- | --- | --- | --- |
| TC-7901 | Controlled E2E | First Provider timeout, second success | Same Job succeeds after exactly two invocations; no Fallback |
| TC-7902 | PostgreSQL/Accounting | Read durable Usage under test owner | Two unique attempt IDs; timeout unavailable/NULL; success complete; same Job |
| TC-7903 | Unit/Negative | Explicit Coordinator-owned mode | Workflow writes no duplicate; absent/multiple owners rejected |
| TC-7904 | Security/Regression | Relay/Worker with synthetic data | Identifier-only Queue, no leakage, no customer/paid/Hosted path |
| TC-7905 | Regression | Legacy AI-01 execution and repository gates | Existing Workflow-owned Usage unchanged; full gates pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
| --- | --- | --- | --- |
| TC-7901, TC-7902, TC-7904 | `npm run test:provider-timeout-recovery-e2e` on dedicated DB/Redis | 0077 baseline PASS; API negative 4 PASS; Worker negative 9 PASS; `CONTROLLED_0079_E2E=PASS`, `CONTROLLED_0079_GATE=PASS` | PASS |
| TC-7902 | PostgreSQL row assertions in controlled API harness | Exactly two distinct attempt IDs on the same Job; retry 0 failed/unavailable with NULL token/cost; retry 1 success/complete | PASS |
| TC-7903 | Focused AI-01 Application tests | 28 passed, including Coordinator-owned no-write and ambiguous-owner rejection | PASS |
| TC-7903, TC-7905 | Direct Worker-role Ledger PostgreSQL regression | One test passed: two inserts of same attempt under `aria_worker` produce one row/metric | PASS |
| TC-7905 | `npm test` | Node/Web/Eval PASS; API 610 passed/1 Hosted-only skipped; Worker 188 passed/0 skipped | PASS |
| TC-7905 | `npm run lint`, `npm run typecheck`, `npm run build` | All passed; strict Python typecheck API 164 files and Worker 69 files | PASS |
| TC-7904 | `npm run scan:secrets` | 942 publishable text files inspected; no finding | PASS |
| TC-7905 | `git diff --check` | No whitespace errors (Git only warned about platform line-ending conversion) | PASS |
| TC-7905 | `npm run validate` | Architecture/development-record gate passed after final records | PASS |

## Failures and Corrections

Contract-first tests initially failed before the explicit single-writer mode
was implemented. The sandboxed `uv` cache was inaccessible; local virtual
environment execution was used for focused tests. The first controlled E2E
failed with SQLSTATE 42501 under `aria_worker` because the Ledger named the
conflict target. Targetless `DO NOTHING` restored INSERT-only operation with
no grant change. A rerun found an immutable price row left by the earlier
attempt; fixture insertion became idempotent and now verifies the exact
zero-rate identity. Temporary safe SQLSTATE diagnostics were removed before
the final E2E and full repository gates. The first full `npm test` run failed
only because the 0069 static contract still required the old conflict target;
the test was updated to require targetless conflict handling and direct
Worker-role PostgreSQL proof, then the entire suite passed.

## Deferred Verification

- One unrelated Hosted upload-security test remained skipped. This is not a
  Hosted gate PASS.
- Real Provider quality, customer content, paid accounting, Worker restart,
  Queue redelivery and ambiguous post-Provider recovery remain outside 0079.

## Final Status

**Final status:** PASS for the isolated synthetic E2E-04 gate under `aria_worker`.
