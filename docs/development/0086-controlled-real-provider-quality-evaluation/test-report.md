# Test Report: 0086 Controlled Real-Provider Quality Evaluation

- Increment ID: `0086-controlled-real-provider-quality-evaluation`
- Date: 2026-10-03
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Python 3.12
- Node.js 24 / npm 11
- Provider generation calls: none
- Non-generation Provider preflight: OpenAI model retrieval attempted once and failed closed
- Customer content: none

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-8601 | REQ-8601/8602 | Exact 60 fixtures and two approved candidates produce the 120-case matrix | PASS |
| TC-8602 | REQ-8602 | Missing explicit paid-synthetic confirmation fails before remote preflight | PASS |
| TC-8603 | REQ-8601/8604 | Reservation is exactly USD 24.945 and calls never exceed 120 | PASS |
| TC-8604 | REQ-8602 | Oversized input fails before model retrieval or Provider invocation | PASS |
| TC-8605 | REQ-8603 | Timeout with unavailable accounting stops after one invocation; no Retry/Fallback | PASS |
| TC-8606 | REQ-8604 | Actual cost uses pinned Catalog Price and Usage; missing accounting stops the run | PASS |
| TC-8607 | REQ-8605 | Provider adapters transmit 25k and medium reasoning/thinking controls | PASS |
| TC-8608 | REQ-8606 | Safe report excludes output; local bundle writes and deletes synthetic review data | PASS |
| TC-8609 | REQ-8607 | All 60 requests expose only approved inputs and fit the 8,000-byte ceiling | PASS |
| TC-8610 | REQ-8607 | Gold, annotations, scoring metadata and Provider IDs stay outside request/canonical identity | PASS |
| TC-8611 | REQ-8608 | Provider Critical is rejected; deterministic Rule Pack owns final classification | PASS |
| TC-8612 | REQ-8609 | PostgreSQL resolves both prices and `aria_worker` inserts one synthetic Usage row | PASS |
| TC-8613 | REQ-8602/8603 | Real-candidate composition is side-effect-free and retains one-attempt/single-writer policy | PASS |
| TC-8614 | REQ-8610 | Complete two-Candidate review import reproduces frozen metrics and emits no content | PASS |
| TC-8615 | REQ-8610 | Extra/free-text review fields, incomplete inventories and unstable percentile behavior fail closed | PASS |
| TC-8616 | REQ-8613 | Paid matrix and two-reviewer adjudication remain disabled and deferred without weakening safety gates | PASS |
| TC-8617 | REQ-8611 | Exact official Price rows provision atomically/idempotently and conflicting Catalog state fails closed | PASS |
| TC-8618 | REQ-8612 | Manual CLI requires exact confirmation/config, materializes deterministic metadata and emits only safe command output | PASS |
| TC-8619 | REQ-8612 | Failed remote model retrieval identifies only the bounded Provider and suppresses raw SDK/credential detail | PASS |

## Commands and Results

```text
node --test scripts/test/controlled-real-provider-evaluation-contract.test.js
PASS — 8 passed

node --test scripts/test/context-evaluation-contract.test.js scripts/test/provider-quality-comparison.test.js
PASS — 11 passed

pytest focused Prompt/Schema and runtime composition units
PASS — 33 passed in the final focused run

pytest PostgreSQL price/Usage preflight
PASS — 3 passed

ruff focused files
PASS

mypy apps/worker/app packages/backend-application/src
PASS — 79 source files

npm run test:ci
PASS — 208 contract/CI tests

npm test (with local PostgreSQL and worktree-local uv cache)
PASS — Web 40; API 612 passed/1 hosted-only skipped; Worker 240 passed/2 environment-specific skipped

npm run typecheck
PASS — Web; API 167 source files; Worker 80 source files

npm run validate
PASS — 23 architecture and development-record checks

node --test scripts/test/provider-evaluation-price-provisioning-contract.test.js
PASS — 3 passed

npm run provision:0086-prices (isolated aria_0086_test PostgreSQL)
PASS — exact two-row Catalog provision completed without Provider calls

controlled migration + npm run provision:0086-prices (fresh aria_0086_eval PostgreSQL)
PASS — revision 0033; only the two frozen Price Versions; zero Provider calls

pytest apps/api/tests/test_eval_price_provisioning.py (isolated migrated PostgreSQL)
PASS — 2 passed; repeated provision remained idempotent

npm run lint:api
PASS

npm run lint
PASS — Web ESLint; API and Worker Ruff

npm run typecheck:api
PASS — 167 source files

pytest apps/worker/tests/test_provider_quality_evaluation_command.py
PASS — 9 passed against the isolated PostgreSQL database, including repeated synthetic Account provisioning

npm run eval:0086:run (required env intentionally absent)
PASS (negative gate) — exits non-zero with only paid_evaluation_confirmation_required; zero DB/Provider side effects

npm run test:records
PASS — 6 passed

manual 0086 remote preflight with explicit credentials and isolated PostgreSQL
PASS (negative gate) — bounded openai_model_preflight_failed; zero paid generation, zero Accounts,
zero Usage records

$env:UV_CACHE_DIR=<worktree-local>; npm test (post-deferral repository rerun)
PASS — contracts 208, eval 35, Web 40, API 457 passed/156 environment-gated skipped,
Worker 208 passed/36 environment-gated skipped

npm run validate (post-deferral)
PASS — 23 architecture and development-record checks
```

The three intentional environment skips were the hosted Supabase sentinel, real Redis publisher
evidence and the dedicated `aria_0077_test` role-migration database. They are unrelated to the
0086 Prompt/Schema or PostgreSQL preflight and are not reported as PASS evidence for those gates.

## Security and Leakage Evidence

- No paid Provider generation call was executed. One non-generation OpenAI model lookup failed
  closed before evaluation state or Usage persistence.
- No Provider credential value was read, printed or logged.
- Safe-report tests prove normalized synthetic output is omitted.
- Review bundles are restricted to `.local/eval-review-bundles/`, ignored by Git and explicitly
  deletable.
- No prompt, raw response, fixture/Gold content or review note enters operational reporting.
- Request contamination tests prove Provider-visible inputs exclude fixture identity, Gold,
  annotations, expected output/count and scoring metadata.
- Review-import tests reject unapproved/free-text fields and safe comparison output contains no
  generated/Gold content, provenance or review notes.
- Manual-command configuration secrets are repr-hidden; console output is an allowlisted safe
  summary and normalized outputs remain beneath the ignored local review-bundle root.

## Execution Results

- The exact 60-fixture inventory materialized through the approved AI-01/AI-02/AI-03 package.
- All 60 serialized requests fit the 8,000 UTF-8 byte contract.
- Both approved candidates resolved and the worst-case reservation calculated to USD 24.945.
- Local migrations through `0033` succeeded; real PostgreSQL Catalog/Worker Usage preflight passed
  without a Provider call.
- A simulated complete run stopped at exactly 120 single attempts and remained below USD 25.
- A simulated timeout with unavailable accounting stopped after one call without retry.
- No real credential, model retrieval or paid generation was executed. The PostgreSQL preflight
  appended exactly one synthetic Usage row through the Worker role, as required by TC-8612.
- The frozen real-price provisioning command was verified structurally and against PostgreSQL. It
  was not run against an external database because no external isolated evaluation `DATABASE_URL`
  was supplied. It ran successfully against the local throwaway `aria_0086_test` database after
  migrations through `0033_durable_retry_checkpoint`.
- The manual paid-evaluation command was verified through its no-env fail-closed gate and unit
  contract. No real credential, remote model lookup or paid generation occurred.
- A fresh local `aria_0086_eval` database was migrated through `0033` and provisioned with only the
  two exact frozen Price Versions. The earlier test database was not reused because test-generated
  catalog rows made it unsuitable for controlled paid evidence.
- The first authorized remote preflight failed before Account creation, Usage persistence or paid
  generation. Database verification showed zero Accounts and zero Usage records.

## Final Status

**Final status:** PASS

The harness implementation, Prompt/Schema package, repository-wide code/test gates, isolated
PostgreSQL preflight and safe remote-preflight failure pass. ADR-073 explicitly defers the paid
matrix and human review until after the MVP feature cycle. This is not a Model Quality Gate PASS
and authorizes no Provider promotion, customer content or Hosted execution.
