# Development Record: 0069 AI Failure Tests

- Increment ID: `0069-ai-failure-tests`
- Date: 2026-09-20
- Owner: AI/Platform Engineering
- Related story: `S1-L05 — AI Failure Tests`
- [Test report](./test-report.md)

## Scope

Implement the frozen Provider-neutral technical Retry and Fallback capability, deterministic
failure tests and idempotent Usage accounting. Primary is limited to initial plus one technical
retry; an explicitly Quality-and-Budget-authorized Fallback receives one invocation and no retry.
Every actual Provider invocation is metered independently. Unknown Usage remains NULL rather than
becoming a fabricated zero. Real Provider promotion, runtime candidate wiring and customer-content
execution remain excluded.

## Source Documents

- Owner-approved and frozen `0069 — S1-L05 AI Failure Tests` contract and Provider invocation
  budget, 2026-09-20.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-L05, Job/Usage test cases and Sprint DoD; synced 2026-09-20.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), Retry, Fallback, Usage/Cost, Logging and Failure UX; synced 2026-09-20.
- [ADR-021](../../adr/ADR-021-ai-execution-port.md),
  [ADR-024](../../adr/ADR-024-usage-ledger-and-worker-role.md),
  [ADR-027](../../adr/ADR-027-context-validation-repair.md),
  [ADR-055](../../adr/ADR-055-provider-adapter-candidates.md) and
  [ADR-056](../../adr/ADR-056-ai-failure-policy.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6901 | Frozen Retry contract | `ProviderFailureCoordinator`; Primary max two calls; SDK retry remains disabled | TC-6901, TC-6902 |
| REQ-6902 | Retry classification | Retry only mapped `timeout`, `rate_limited`, `provider_unavailable` with `retryable=true` | TC-6902, TC-6903 |
| REQ-6903 | Full Jitter | Injected sleeper/random; `min(4s, 1s * 2^retry_no)` | TC-6902 |
| REQ-6904 | Invalid response stages | Unparseable response is terminal; parsed/schema-invalid remains H03 Repair concern | TC-6903, TC-6904 |
| REQ-6905 | Fallback authorization | Explicit port requires Quality and Budget; missing/error/deny fail closed | TC-6905 |
| REQ-6906 | Invocation budget | Primary 2 + one-shot Fallback 1; terminal Fallback failure; maximum total 3 | TC-6906 |
| REQ-6907 | Attempt accounting identity | `provider_attempt_id UUID NOT NULL UNIQUE`; every real retry/Fallback gets a new ID | TC-6907, TC-6910 |
| REQ-6908 | Persistence idempotency | PostgreSQL unique constraint and Worker `ON CONFLICT DO NOTHING`; duplicate replay emits neither financial row nor usage metric | TC-6907, TC-6910 |
| REQ-6909 | Honest unknown cost | `accounting_status`; unavailable failed Usage requires NULL token/cost fields | TC-6908, TC-6910 |
| REQ-6910 | Usage-bearing failure | Valid numeric Usage on malformed structured output is priced and stored as complete failed Usage | TC-6904, TC-6909 |
| REQ-6911 | Safe observability | Bounded lifecycle logs; no prompt/input/output/raw error/customer content or attempt-ID metric label | TC-6911 |
| REQ-6912 | No runtime promotion | Synthetic fakes only; no composition-root Primary/Fallback or paid Provider call | TC-6912 |

## Assumptions and Clarifications

The owner froze both the retry/fallback policy and the total invocation budget. Primary may execute
twice; Fallback is considered only after exhausted Primary timeout/provider-unavailable failures,
requires explicit Quality and Budget authorization, executes once and is terminal on failure.
`rate_limited` receives one technical retry but never triggers Fallback. Provider response parsing
and schema/business validation are intentionally distinct failure stages.

**Unapproved assumptions:** None

## Changes

- Added Migration 0024 with unique Provider attempt identity, complete/unavailable accounting and
  strict DB coherence constraints. Historical complete rows receive generated unique identities;
  unsafe downgrade with unavailable rows fails instead of inventing zero Usage.
- Made Worker Ledger persistence idempotent for an identical `provider_attempt_id` while preserving
  append-only UPDATE/DELETE denial and worker-only authority.
- Added the Provider-neutral failure coordinator with bounded retry, injected Full Jitter and
  fail-closed Fallback authorization.
- Preserved safe numeric Provider Usage on malformed structured output so these failed invocations
  remain completely priced without storing raw output.
- Propagated stable attempt identity through the shared AI execution response and all existing
  Context, Requirement, Gap and Scope metering paths.
- Added ADR-056, updated affected architecture/Worker/Usage mirrors and added contract, unit,
  integration and negative leakage tests.

## Architecture and Design Decisions

- Technical Retry is Application policy; Provider SDK adapters remain single-attempt Infrastructure
  boundaries. Semantic Repair remains separate and increments `repair_no`, not Provider policy.
- Pricing resolves before each actual paid invocation. Ledger append failure is fail-closed and no
  subsequent Provider call is made by the coordinator.
- `provider_attempt_id` is generated immediately before adapter invocation. Persistence replay
  reuses the immutable record; a real second call receives a new ID.
- Fallback selection is caller-supplied capability only. There is no registered runtime Primary,
  Fallback, provider order, customer-data path or external network call in this increment.
- The existing modular monolith remains unchanged: shared contracts live in backend Application,
  the execution coordinator lives in Worker Application and SDK translation stays in Worker
  Infrastructure.

## Structure Preservation

- No new deployable, API endpoint, UI route, Queue, scheduler or public Usage read API was added.
- Domain/shared Application code imports no Provider SDK or framework.
- PostgreSQL remains the authoritative append-only Usage source; Queue/Provider responses are not
  canonical state.
- Existing Provider candidates remain evaluation-only and absent from the composition root.
- Repository documents mirror the Canonical Drive decisions and identify their source links and
  sync date.

## Senior Review

- PASS: maximum invocation budget is structurally bounded at three and Fallback never retries.
- PASS: first-attempt Primary success stops immediately; permanent/invalid failures never retry;
  rate limit retries once but cannot trigger Fallback.
- PASS: missing, denied or failing Fallback policy is fail-closed and does not invoke a candidate.
- PASS: every actual call receives a distinct attempt identity; persistence duplication for one ID
  cannot create another financial record or usage metric.
- PASS: Timeout without Usage produces NULL accounting, while malformed output with safe Provider
  Usage produces a complete failed priced record.
- PASS: Ledger failure prevents another Provider invocation, avoiding unmetered retry.
- PASS: logs contain only bounded metadata; request, prompt, response, policy exception text,
  customer/fixture content and credentials are absent.
- PASS: no real Provider promotion, credential, paid request or customer content was introduced.

## Verification

See [test-report.md](./test-report.md). Contract, Worker and API-focused suites passed, including
Migration 0024 against local PostgreSQL 16. The complete repository regression passed with the
single previously environment-gated hosted test skipped. No external Provider request was made.

## Remaining Risks

- Real Provider promotion and live fallback behavior still require a separate routing/promotion
  decision, synthetic quality evidence, controlled secrets and Platform-provisioned Price rows.
- A Provider timeout may be billable while Usage is unavailable. The Ledger records that
  uncertainty honestly; later reconciliation/budget treatment requires a separate contract.
- This policy does not add Queue-level retry, Job lease/exhaustion handling or a continuous Outbox
  scheduler.

**Final status:** PASS
