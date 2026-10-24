# Test Report: 0077 Controlled Synthetic Context-to-Scope E2E

- **Status:** PASS — isolated synthetic gate under `aria_worker`
- **Increment ID:** `0077-controlled-synthetic-context-to-scope-e2e`
- [Development record](./development.md)

## Environment

Dedicated `aria_0077_test` PostgreSQL 16 database on local Docker; Redis 7 DB 15
on local Docker; Python 3.12, API/Worker virtual environments, Celery publisher,
deterministic Fake Providers and `context_to_scope_synthetic_fa_v1` fixture
(`fa_ctx_scope_0077_001`). No customer, paid or hosted execution. The runner
rejects every database name outside `aria_0077_test...` before migration/reset.

## Test Cases and Results

| ID | Type | Expected result | Actual | Status |
| --- | --- | --- | --- | --- |
| TC-7701 | End-to-end | AI-01 establishes N; explicit AI-02/03/05 jobs produce one Draft @ N | `CONTROLLED_0077_E2E=PASS` under `aria_worker`; one Draft and succeeded AI-05 Job | PASS |
| TC-7702 | Version continuity | Downstream jobs retain N and pinned revisions; no hidden repin | Harness asserts each `payload_ref.context_version=N`; API/Worker pinned-input tests passed | PASS |
| TC-7703 | Critical Gap/human command | Open Critical blocks AI-05; authorized dismissal permits a new command | No blocked Job; existing `ClarificationService.dismiss_gap` transitioned synthetic Gaps; subsequent AI-05 succeeded | PASS |
| TC-7704 | Delivery | Job/Outbox atomic, ID-only envelope, expected Celery task routing | Four local Relay→Redis/Celery→`aria_worker` roundtrips; exact three-key message asserted | PASS |
| TC-7705 | Replay/conflict | Duplicate delivery has no duplicate effects; existing Draft cannot be overwritten | `already_completed` on redelivery; one Draft; scheduler rejects existing Draft | PASS |
| TC-7706 | Failure | Changed pinned input fails closed; final commit failure leaves no Draft/Job success | PostgreSQL Scope Worker regressions executed and passed | PASS |
| TC-7707 | Isolation | Tenant crossing cannot schedule or finalize foreign resource | API 3 and Worker 3 Tenant A/B PostgreSQL parameter cases passed | PASS |
| TC-7708 | Safety | Non-test DB rejected before mutation; no fixture/generated text in output; queue cleaned | Wrong DB rejected; leakage checks passed; Redis DB-15 scan returned no `aria_0077_*` keys | PASS |
| TC-7709 | Repository gate | `npm test`, `npm run validate`, lint/typecheck | Full tests, lint and typecheck passed; development-record validation passed after finalizing both records | PASS |
| TC-7710 | Privilege/isolation | AI-02/03 helpers lock only exact Job/tenant/version rows; direct Worker writes and public EXECUTE denied | Dedicated PostgreSQL test passes positive calls, mismatched tenant rejection, bounded lock interference, Worker write denial and helper-owner RLS checks | PASS |
| TC-7711 | Migration safety | 0030 upgrade/downgrade preserve least privilege without destructive cascade | Dedicated PostgreSQL downgrade and re-upgrade both passed after explicit schema-grant cleanup | PASS |

## Execution Results

- `npm run test:context-to-scope-e2e` with dedicated `TEST_DATABASE_URL` and local
  `TEST_REDIS_URL`: PASS under `aria_worker`, including 4 API and 9 Worker
  PostgreSQL cases. The prior owner-role-only pass is superseded as evidence.
- Migration 0030 downgrade/re-upgrade: PASS in `aria_0077_test` only. No broad
  Worker grant or schema cascade was used.
- `npm test` with `TEST_DATABASE_URL` and `TEST_QUEUE_BROKER_URL`: PASS; API
  608 passed, 1 hosted-only skipped; Worker 188 passed, 0 skipped; Node/Web/Eval
  suites passed.
- `npm run lint`, `npm run typecheck` and focused Ruff: PASS.
- Final rerun after the owner's 2026-09-28 scope clarification: controlled E2E
  PASS under `aria_worker`; 4 API + 9 Worker PostgreSQL cases PASS; `npm test`
  PASS (API 608 passed/1 hosted-only skip; Worker 188 passed/0 skipped).
- Read-only role audit in the two-tenant synthetic database: direct
  `aria_worker` SELECT saw rows from two distinct Accounts in both
  `context_items` and `requirements`. This is an existing policy exposure,
  explicitly deferred by the owner to a separate security architecture
  contract, not a failure of the new helper's scoped, content-free calls.
- `npm run validate`: PASS after both 0077 records were finalized; the
  development-record convention was not bypassed or weakened.

## Final Status

**Final status:** PASS for the isolated, synthetic 0077 gate under the actual
`aria_worker` runtime principal. The owner clarified that only the new
helper/Job path is tenant-scoped in 0077; pre-existing raw `aria_worker`
`SELECT`/RLS remains unchanged and is a deferred, independent security concern.
One hosted upload-security skip remains INCOMPLETE hosted evidence, not a result
of this local gate. Real-provider quality, human UX, K05 publication, customer
content, product activation and full Login-to-Scope acceptance remain outside
0077.
