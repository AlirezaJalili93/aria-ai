# Development Record: 0086 Controlled Real-Provider Quality Evaluation

- Increment ID: `0086-controlled-real-provider-quality-evaluation`
- Date: 2026-10-03
- Owner: Platform/AI Evaluation Engineering
- Related workflows: `AI-01`, `AI-02`, `AI-03`
- [Test report](./test-report.md)

## Scope

Build the fail-closed, manually authorized evaluation boundary for comparing only OpenAI
`gpt-5.6-terra` and Google `gemini-3.8-flash` over the 60 approved synthetic fixtures per
candidate. Enforce the exact 120-case matrix, 8,000-byte request limit, 25,000 output-token limit,
USD 25 hard budget, one metered invocation per case and temporary local-only review evidence.
Do not promote a Provider, process customer content, retry, Repair, Fallback or activate Hosted
execution.

## Source Documents

- Owner-approved frozen `0086 — Controlled Real-Provider Quality Evaluation` numeric contract,
  2026-09-30.
- Owner-approved `Prompt/Output-Schema Package v1` for AI-01/AI-02/AI-03, 2026-09-30.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H05, S1-I05, S1-J05 and AI Release Gate; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — Evaluation Mode, Usage/Cost and Release Gate; reread 2026-09-30.
- [ADR-072](../../adr/ADR-072-controlled-real-provider-quality-evaluation.md).
- [OpenAI GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) and
  [Reasoning models](https://developers.openai.com/api/docs/guides/reasoning); verified
  2026-09-30.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-8601 | Owner 0086 numeric contract; ADR-072 hard caps | Exact 60×2 inventory and invocation/input/output/budget constants | TC-8601, TC-8603 |
| REQ-8602 | Owner preflight contract | Manual confirmation, manifest validation, model retrieval, immutable Price resolution and full reservation before generation | TC-8601, TC-8602, TC-8604 |
| REQ-8603 | Owner no retry/repair/fallback | Evaluation-only one-attempt policy over the existing single Usage writer | TC-8605 |
| REQ-8604 | Owner per-call budget guard | Pinned Price Version, conservative next-call guard and authoritative Usage-derived cost | TC-8603, TC-8606 |
| REQ-8605 | Owner reasoning/output controls | Explicit OpenAI standard/medium and Gemini medium with 25,000-token ceiling | TC-8607 |
| REQ-8606 | Owner evidence boundary | Safe report excludes content; review output is temporary under ignored local storage | TC-8608 |
| REQ-8607 | Owner Prompt/Output-Schema Package v1 | Separate immutable AI-01/02/03 prompts, exact Provider-visible inputs and strict candidate schemas | TC-8609, TC-8610 |
| REQ-8608 | Owner AI-03 Critical boundary | Provider cannot classify Critical; validated signals feed `critical_gap_rule_pack_v1` | TC-8611 |
| REQ-8609 | Owner PostgreSQL preflight | Catalog resolution and Worker-only Usage insert execute against migrated isolated PostgreSQL without Provider calls | TC-8612 |
| REQ-8610 | Owner-approved Human Review/alignment continuation; ADR-072 | Strict local review import and safe H05/I05/J05 comparison aggregation with deterministic latency/cost statistics | TC-8614, TC-8615 |
| REQ-8611 | Owner continuation after official Provider-price verification, 2026-10-03; ADR-072 | Explicit Platform-owned provisioning of the two exact immutable Price Versions with UTC date normalization and fail-closed conflict detection | TC-8617 |

## Assumptions and Clarifications

The numeric policy, candidates, fixture sets, Provider settings, execution boundary, retention
behavior and Prompt/Output-Schema Package v1 are owner-frozen. No runtime behavior was inferred
beyond those approved contracts.

**Unapproved assumptions:** None

## Changes

- Accepted ADR-072 with the frozen numeric contract.
- Added a provider-neutral preflight and execution coordinator with exact inventory, identity,
  serialization, Price Version, reservation and per-call budget enforcement.
- Added an evaluation-only invocation policy to the existing 0069 single-writer coordinator:
  one Primary attempt, no retry and no Fallback.
- Sent the frozen output/reasoning settings explicitly through both approved Provider adapters.
- Added non-generation model retrieval preflight for the two approved model IDs.
- Added exact immutable fixture-manifest loading behind a required versioned request factory.
- Added the approved, distinct AI-01/AI-02/AI-03 Prompt/Output-Schema Package v1. Provider requests
  contain only approved workflow inputs and never contain Gold, annotations or scoring metadata.
- Added post-Provider schema/business/provenance normalization with harness-controlled Candidate
  IDs. Stable synthetic Source/Requirement aliases are preserved for deterministic scoring while
  UUIDv5 identities remain internal to Domain validation. AI-03 Critical classification runs only
  through the deterministic versioned Rule Pack.
- Added safe execution report projection and ignored, deletable local review bundles.
- Added a real PostgreSQL preflight test for approved candidate prices and `aria_worker` Usage
  insertion; it performs zero Provider calls and uses only synthetic identities.
- Added manual-only real-candidate composition for the existing model preflight, Price Catalog,
  single Usage writer and strict output normalizer. Construction starts no run or network call.
- Added the strict `provider-quality-human-review-v1` import schema and safe comparison builder. It
  reuses the executable H05/I05/J05 evaluators, enforces exact alignment/reviewer inventories,
  rejects free-text fields and emits content-free quality, cost, token, failure and nearest-rank
  latency evidence.
- Added contract, unit, PostgreSQL, leakage-negative and adapter tests.
- Added an explicit, transaction-locked and idempotent Platform provisioning command for the two
  verified 0086 Price Versions. It requires an isolated-database confirmation, grants no Runtime
  write access, makes no Provider call and rolls back when an existing Catalog row differs.

## Structure Preservation

- Domain/Application remains free of OpenAI, Google, SQLAlchemy and filesystem imports.
- Provider SDK model checks and local fixture/evidence adapters remain in Worker Infrastructure.
- Usage stays single-writer through `ProviderFailureCoordinator`; the evaluation coordinator does
  not create a parallel cost ledger.
- No endpoint, Queue task, scheduler, deployable service, production routing or Hosted execution
  was introduced.
- Real-candidate composition is dependency wiring only; it has no executable entry point and cannot
  start an Eval Run without an explicit caller and successful preflight.
- Customer content is rejected by the case contract and no Provider call has been made.

## Senior Review

- PASS: preflight has zero generation side effects and rejects incomplete matrices, unapproved
  candidates, oversized requests, missing confirmation, missing models and missing prices.
- PASS: planned maximum reservation is exactly USD 24.945 under the frozen Catalog rates.
- PASS: one-attempt policy cannot use Retry, Repair or Fallback.
- PASS: both adapters transmit explicit reasoning and output ceilings.
- PASS: safe reports omit normalized output and the review bundle is ignored and deletable.
- PASS: all 60 approved requests fit the 8,000-byte ceiling and expose only approved input fields;
  contamination-negative tests reject fixture/Gold/evaluator metadata.
- PASS: invalid outputs fail without repair, Candidate IDs are harness-owned, and AI-03 cannot set
  Critical severity.
- PASS: migrated PostgreSQL Catalog and `aria_worker` Usage writer preflight passed locally with no
  Provider invocation.
- PASS: deterministic review import reproduces H05/I05/J05 metrics and blockers for both Candidate
  matrices without copying prompts, generated/Gold text, provenance or reviewer notes into the
  safe comparison report.
- PASS: the two officially verified Price Versions provisioned twice without duplicates in a fresh
  migrated `aria_0086_test` PostgreSQL database; exact-row verification passed after each run.
- PENDING: remote credential/model preflight, controlled paid execution and human adjudication.

## Verification

See [test-report.md](./test-report.md). Focused contract, unit, lint, typecheck and repository-wide
test gates pass. Architecture validation remains truthfully non-PASS only because 0086 itself is
PENDING; paid synthetic execution and human adjudication remain pending.

## Remaining Risks

- Prompt/schema quality remains unproven until both real candidates complete the controlled run;
  their versions are now frozen rather than inferred from fake-provider fixtures.
- Local PostgreSQL Catalog/Usage preflight passed. Remote credential and Provider model retrieval
  have not been executed.
- Human review/adjudication and temporary bundle deletion have not run on real outputs.
- The verified Price Versions now have an executable provisioning path, but no external database
  was changed because an isolated evaluation `DATABASE_URL` was not supplied in this session.
- A PASS will remain evidence only; Provider promotion, customer data and Hosted activation stay
  separate NO-GO gates.

**Final status:** PENDING — controlled paid execution and required human review have not run.
