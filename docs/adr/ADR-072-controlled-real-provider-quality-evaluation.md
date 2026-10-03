# ADR-072 — Controlled Real-Provider Quality Evaluation

- Status: Accepted
- Date: 2026-09-30
- Decision owner: Product and Engineering
- Extends: ADR-029, ADR-034, ADR-040, ADR-054, ADR-055, ADR-056 and ADR-069–071

## Context

The deterministic H05, I05 and J05 harnesses prove their schemas, calculations and regression
machinery, but they do not establish real-model quality. ADR-055 approved OpenAI
`gpt-5.6-terra` and Google `gemini-3.8-flash` as evaluation candidates only. The owner approved
0086 for contract definition to compare those candidates on the same synthetic, versioned data
without selecting a Primary, enabling Fallback, processing customer content or activating Hosted
execution.

The current fixture inventory is exact:

| Eval suite | Version | Fixtures per candidate |
|---|---|---:|
| Context Structuring | `context_structuring_eval_v1` | 20 |
| Requirement Extraction | `requirement_extraction_eval_v1` | 20 |
| Gap Detection | `gap_detection_eval_v1` | 20 |

Two candidates therefore require 120 planned Provider invocations when every case is attempted
exactly once. A fail-closed budget needs an output-token ceiling; neither reporting a cost after the
run nor relying on a Provider default is sufficient.

## Decision

### Evaluation boundary

- The run is explicit and manual. It has no public endpoint, Queue trigger, workflow chaining,
  scheduler or Hosted composition.
- Only the three immutable synthetic fixture sets above are eligible. Customer content,
  customer-derived fixtures and production prompts are prohibited.
- Candidate identity is fixed to ADR-055. No additional Provider or model is accepted.
- Each candidate receives the same fixture IDs, fixture-set versions, workflow version, prompt
  version, output-schema version and evaluation-rule version.
- Tools, Search, Function Calling, Provider-side cache creation, SDK retries, semantic Repair and
  Fallback remain disabled.
- Reasoning configuration is explicit and pinned: OpenAI uses `mode=standard, effort=medium` and
  Gemini uses `thinking_level=medium`. Sampling parameters remain unset. The comparison does not
  rely on Provider defaults that may change independently.
- A case has one Provider invocation. A Provider failure is evidence and is not retried by 0086.

### Frozen hard caps

```text
max_total_invocations              = 120
max_invocations_per_candidate      = 60
max_invocations_per_candidate_case = 1
max_serialized_request_utf8_bytes  = 8_000
max_output_tokens_per_invocation   = 25_000
max_total_estimated_budget         = USD 25.00
```

The 8,000-byte input ceiling is deliberately a conservative token upper bound for the exact
serialized instructions, input and JSON schema. A request above that bound fails before any paid
call. Both Provider adapters must send the 25,000-token output ceiling explicitly; it must not be a
report-only value. This retains the current official OpenAI starting headroom recommendation for
reasoning plus visible output, avoiding a comparison that systematically truncates one candidate.

At the ADR-055 documented rates, the full worst-case reservation is:

```text
OpenAI: 60 × ((8,000 × $2.00/M) + (25,000 × $12.00/M)) = $18.960000
Gemini: 60 × ((8,000 × $0.75/M) + (25,000 × $3.75/M)) = $5.985000
Total                                                         = $24.945000
Hard cap                                                      = $25.000000
```

Cached input is reserved at the higher normal-input rate. The calculation uses `Decimal` and the
exact immutable Catalog rows resolved for the run, not price literals embedded in the harness. If
the Catalog rates produce a reservation above USD 25.00, the whole preflight fails with zero paid
calls.

### Frozen evaluation Price Versions

The Provider source pages publish price-effective calendar dates rather than timestamps. For this
Platform Catalog, a published date is normalized to `00:00:00Z` on that date. This normalization is
part of the controlled 0086 contract and is not represented as a Provider-published wall-clock
time.

| Provider/model/tier | Pricing version | Effective from | Input / Cached input / Output per 1M USD |
|---|---|---|---:|
| OpenAI `gpt-5.6-terra` Standard | `openai-gpt-5.6-terra-standard-2026-07-30` | `2026-07-30T00:00:00Z` | `2.00 / 0.20 / 12.00` |
| Google `gemini-3.8-flash` Standard introductory | `google-gemini-3.8-flash-standard-intro-2026-09-02` | `2026-09-02T00:00:00Z` | `0.75 / 0.075 / 3.75` |

OpenAI cache-write pricing is not represented by the three-rate Catalog. ADR-055 therefore remains
authoritative: explicit cache behavior must produce zero `cache_write_tokens`; missing, malformed
or non-zero usage fails closed. Gemini Context Cache creation/storage remains disabled. The Google
introductory row may be used only through 2026-12-31; an evaluation on or after 2027-01-01 requires
a separately approved Price Version before any Provider call.

Provisioning is an explicit Platform operation against the isolated evaluation database. It uses a
short transaction and a transaction-scoped advisory lock, inserts both rows as one unit, accepts an
exact existing match as idempotent, and rolls back on any missing or conflicting field. Runtime
roles receive no new write privilege and neither migrations nor application startup seed prices.

### Preflight and budget enforcement

Before the first paid call the harness must:

1. validate the exact fixture manifests and the complete 120-case inventory;
2. pin the run identity and hash its immutable execution manifest;
3. require both credentials without exposing their values;
4. use the Providers' non-generation model retrieval APIs to authenticate and verify the exact
   approved model IDs;
5. resolve and pin both immutable Price Versions for the planned execution instant;
6. materialize every Provider request and reject any request above 8,000 UTF-8 bytes;
7. compute the worst-case reservation for all 120 calls with the 25,000-token output ceiling; and
8. fail before any generation when any check fails or the reservation exceeds USD 25.00.

During execution, a guard checks the invocation count and remaining monetary budget immediately
before every Provider call. Reaching either cap stops all remaining cases. A Provider response
whose reported usage exceeds the enforced request ceilings is an accounting violation: retain the
single authoritative Usage record, stop the run and do not continue.

### Run identity and accounting

Every run pins at least:

```text
eval_run_id
harness_version
eval_suite_version
fixture_set_version
candidate provider/model
workflow_version
prompt_version
schema_version
pricing_version
evaluation_rule_version
reasoning_configuration_version
execution_manifest_hash
```

The harness uses an isolated PostgreSQL database and provisions only synthetic Account/Project/Job
identities required by the existing foreign keys. Provider execution uses the existing Price
Catalog, `provider_attempt_id`, Usage Ledger and single-writer accounting paths. It must not create
a parallel cost table or calculate an authoritative cost from report data. One actual invocation
equals one durable attempt identity and one Usage record. The evaluation Account and Project are
not customer or production identities.

### Prompt, input and output-schema package v1

The three Provider contracts are independent and immutable for a run:

| Workflow | Prompt version | Provider-visible input | Output schema |
|---|---|---|---|
| AI-01 | `ai-01-real-eval-prompt-v1` | `project_type`, `sources` | `candidate-context-batch-v1` |
| AI-02 | `ai-02-real-eval-prompt-v1` | `project_type`, `context_version`, `context_items` | `candidate-requirement-batch-v1` |
| AI-03 | `ai-03-real-eval-prompt-v1` | `project_type`, `context_items`, `requirements`, `completion_checklist_v1` | `candidate-gap-batch-rule-signals-v1` |

The Provider never receives fixture identity, Gold/expected output, annotations, expected counts,
scoring rules/results or evaluator-only metadata. Harness-controlled candidate IDs are assigned only
after parse, schema, business and provenance validation. Provider-generated IDs are not canonical.

AI-03 may return Candidate Gaps and untrusted `rule_signals`, but its schema does not permit a
`critical` severity. Final Critical classification belongs exclusively to
`VersionedCriticalGapRuleEvaluator` with `critical_gap_rule_pack_v1`. An invalid schema, business
rule or provenance result is recorded as evaluation failure without Retry, Repair or Fallback.

After the first paid invocation, prompt, schema, fixture set, evaluation rule, completion checklist
and Critical Rule Pack versions are immutable for that run. A change requires a new Eval Run.

### Evidence and human review

The safe comparison report contains only run/version identities, candidate identity, aggregate
and per-fixture metric outcomes, total/average cost, latency p50/p95/max, token totals, failure
counts/classes, blocker categories and human-review scores. It contains no prompt, raw response,
fixture content, generated content, Gold content, source references, credentials or Provider error
text.

Normalized structured outputs required by two-reviewer H05/I05/J05 review are written only to a
separate local review bundle. The bundle is ignored by Git, never uploaded by CI, never logged,
contains synthetic data only and is deleted after adjudicated scores have been imported into the
safe report. A run without required human review remains `awaiting_human_review`; it cannot pass the
Model Quality Gate.

The import contract is `provider-quality-human-review-v1`. Each successful Candidate/fixture case
contains final one-to-one `candidate_id -> matched_gold_id|null` alignment, semantic-unsupported and
duplicate-group annotations, plus exactly two independent rubric scores and any required
adjudication. Context scores are fixture-level; Requirement and Gap scores are Candidate-level.
The import accepts no free-text note or generated/Gold content, must match the execution manifest,
and must cover the successful normalized-output inventory exactly.

Latency uses deterministic nearest-rank percentiles over every actual invocation with non-null
latency: rank `ceil(p*N)` in ascending order for p50 and p95. Empty samples are `N/A`. Cost totals
use the authoritative per-invocation eight-decimal values; average cost is rounded once to eight
decimal places with `ROUND_HALF_UP`. Failure-class counts include all actual failed invocations.

### Comparison and release semantics

- Existing frozen H05/I05/J05 formulas, blockers, N/A rules and reviewer adjudication remain
  authoritative; 0086 does not redefine quality.
- Candidate comparison is valid only when both candidates complete against the same pinned
  execution manifest. Partial results remain failure evidence but cannot select a winner.
- PASS means the controlled synthetic real-Provider evaluation produced complete, reproducible
  quality/cost/latency evidence within both caps.
- PASS does not promote a Provider, select Primary/Fallback, authorize customer content, activate
  Hosted execution or satisfy full Product AI acceptance by itself.

## Observability and security

Allowed operational fields are bounded: `eval_run_id`, `fixture_id`, suite/version identifiers,
candidate provider/model, stage, duration, token counts, calculated cost, status and safe failure
class. Fixture or generated text, prompts, schemas, raw Provider payloads, credentials, review
notes and source references are forbidden in logs and metric labels. `eval_run_id` and
`fixture_id` may be correlation log fields but not metric labels.

## Deferred

- Provider promotion and Primary/Fallback selection.
- Customer-content and production-prompt authorization.
- Hosted, scheduled, Queue-driven or automatically repeated evaluation.
- Technical Retry, Semantic Repair and Fallback during candidate comparison.
- Scope-generation and AI-04 real-Provider evaluation.
- Production data retention for model inputs or outputs.

## Sources

- Owner-approved 0086 contract-definition boundary, 2026-09-30.
- Owner-approved `Prompt/Output-Schema Package v1`, 2026-09-30.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-H05, S1-I05, S1-J05 and AI Release Gate; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), Cost Guard, Evaluation Modes and Release Gate; reread 2026-09-30.
- [OpenAI Models API](https://platform.openai.com/docs/api-reference/models/object) and
  [Responses `max_output_tokens`](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) plus
  [reasoning output headroom guidance](https://developers.openai.com/api/docs/guides/reasoning), verified 2026-09-30.
- [Gemini Models API](https://ai.google.dev/api/models) and
  [GenerateContent `maxOutputTokens`](https://ai.google.dev/api/generate-content) plus
  [Gemini thinking controls](https://ai.google.dev/gemini-api/docs/thinking), verified 2026-09-30.
- [OpenAI GPT-5.6 Terra pricing](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
  and [OpenAI Changelog](https://developers.openai.com/api/docs/changelog), verified 2026-10-03.
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing) and
  [Gemini Release Notes](https://ai.google.dev/gemini-api/docs/changelog), verified 2026-10-03.

**Unapproved assumptions:** None
