# ADR-055 — Evaluation-only Provider Adapter Candidates

- Status: Accepted
- Date: 2026-09-20
- Decision owner: Product and Engineering
- Extends: ADR-021, ADR-022 and ADR-054

## Context

The provider-neutral Gateway and Adapter ports exist, and the immutable Price Catalog must resolve
an exact price before any paid invocation. The owner approved two concrete candidates for synthetic
evaluation only: OpenAI `gpt-5.6-terra` and Google `gemini-3.8-flash`. This decision does not promote
either candidate into runtime routing and does not authorize customer content.

The approved OpenAI cost refinement is material: Responses usage can include
`cache_write_tokens`, while the current Usage Ledger has only normal-input, cached-input and output
rates. Silently discarding that usage would make the ledger inaccurate.

## Decision

### Candidate boundary

- OpenAI candidate: `gpt-5.6-terra`, official `openai==3.16.2` SDK and Responses API.
- Google candidate: `gemini-3.8-flash`, official `google-genai==2.24.0` SDK and GenerateContent API.
- Primary: none.
- Fallback: none.
- Both adapters live in Worker Infrastructure and implement the existing provider-neutral
  `ProviderAdapter`; Domain/Application import neither SDK.
- The provider-independent request has exactly `instructions`, `input` and `output_schema`.
- Structured JSON output is mandatory. OpenAI tools, Search and Function Calling are disabled;
  Gemini tools, automatic Function Calling and Context Cache creation are disabled.
- SDK retries are disabled. Connect timeout is 5 seconds and request/read timeout is 60 seconds.
- Credentials must be non-empty and the model must be the exact approved candidate before a call.
- The immutable Price Catalog resolves before the adapter is invoked, and the exact result is
  retained with the normalized Provider result. Missing Price fails before a paid call.

### Usage normalization

OpenAI maps `input_tokens`, `input_tokens_details.cached_tokens` and `output_tokens`. Implicit cache
writes are disabled with explicit cache mode. `input_tokens_details.cache_write_tokens` must be
present and zero; missing, malformed or non-zero data fails closed with stable code
`provider_accounting_unsupported`/`invalid_response`. Expanding the Ledger and Catalog for a fourth
rate is a later decision if evaluation demonstrates non-zero cache writes.

Gemini maps:

```text
input_tokens        = promptTokenCount
cached_input_tokens = cachedContentTokenCount
output_tokens       = candidatesTokenCount + thoughtsTokenCount
```

Cached input remains a subset of total input for both adapters. Missing required usage or invalid
counts fail closed rather than producing a fabricated zero-cost record.

### Data and evaluation boundary

- Only versioned synthetic fixtures may be sent during candidate evaluation.
- Customer content, production prompts and customer-derived fixtures are prohibited until a
  separate Data/Eval Review approves them.
- No automatic runtime wiring, routing mapping, promotion or fallback is introduced.
- Real API execution needs separately supplied secrets and controlled Price Catalog entries; no
  secret or paid call is part of this increment's automated tests.

The verified public prices at decision time were USD per one million tokens:

| Candidate | Input | Cached input | Output |
|---|---:|---:|---:|
| OpenAI `gpt-5.6-terra` | 2.00 | 0.20 | 12.00 |
| Google `gemini-3.8-flash` through 2026-12-31 | 0.75 | 0.075 | 3.75 |

These values document candidate selection but are not silently seeded into the runtime Catalog.
Catalog `pricing_version` and exact `effective_from` are controlled Platform data and must be
explicitly provisioned before a paid evaluation. Gemini pricing must be reviewed before 2027.

## Error mapping

Adapters map raw SDK errors to the bounded Provider-neutral classes: `timeout`, `rate_limited`,
`auth_error`, `invalid_response`, `safety_block`, `provider_unavailable`, `quota_error` and
`unknown_provider_error`. Raw response bodies, SDK error text, prompts, structured input/output and
credentials never cross this boundary or enter logs.

## Consequences

- G02/G03 have concrete, replaceable Infrastructure adapters without choosing a runtime winner.
- Price absence and unsupported cache-write accounting stop execution instead of corrupting cost.
- Model-quality comparison remains a controlled synthetic evaluation; unit/contract tests prove
  integration semantics, not Provider quality.
- Promotion, fallback, customer-data approval, real Price Catalog provisioning and cache-write
  Ledger expansion remain explicit later decisions.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-G02/G03; synced 2026-09-20.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), Provider Adapter and Evaluation Gate; synced 2026-09-20.
- [Dependency & Vendor Register v1.0](https://docs.google.com/document/d/1AVZdOzMahLmNL9c38q9DObuR1C4R787ROc85FBnLgHE/edit), OpenAI/Google provider entries; synced 2026-09-20.
- [OpenAI model and Responses documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra).
- [OpenAI Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
- [Gemini Structured Outputs documentation](https://ai.google.dev/gemini-api/docs/structured-output).
- [Gemini pricing documentation](https://ai.google.dev/gemini-api/docs/pricing).

**Unapproved assumptions:** None
