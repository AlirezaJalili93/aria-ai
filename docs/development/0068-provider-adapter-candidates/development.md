# Development Record: 0068 Provider Adapter Candidates

- Increment ID: `0068-provider-adapter-candidates`
- Date: 2026-09-20
- Owner: AI/Platform Engineering
- Related stories: `S1-G02 — Provider Adapter A`, `S1-G03 — Provider Adapter B`
- [Test report](./test-report.md)

## Scope

Implement the two approved synthetic-evaluation Provider adapters behind the existing
provider-neutral Worker port: OpenAI Responses with `gpt-5.6-terra` and Google GenerateContent with
`gemini-3.8-flash`. Enforce Structured Output, disabled tools/retries, bounded timeouts, safe error
mapping, pre-call Price resolution, normalized token accounting and fail-closed OpenAI cache-write
handling. Runtime promotion/fallback, customer data, live model-quality evidence and automatic
routing are excluded.

## Source Documents

- Owner-approved and frozen `0068 — S1-G02/G03 Provider Adapters` contract and required
  cache-write refinement, 2026-09-20.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-G02/G03; synced 2026-09-20.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), Provider Adapter, structured validation,
  metering and Evaluation Gate; synced 2026-09-20.
- [Dependency & Vendor Register v1.0](https://docs.google.com/document/d/1AVZdOzMahLmNL9c38q9DObuR1C4R787ROc85FBnLgHE/edit), OpenAI/Google provider boundaries; synced
  2026-09-20.
- [ADR-021](../../adr/ADR-021-ai-execution-port.md),
  [ADR-022](../../adr/ADR-022-generic-provider-adapter-port.md),
  [ADR-054](../../adr/ADR-054-provider-price-versioning.md) and
  [ADR-055](../../adr/ADR-055-provider-adapter-candidates.md).
- Official OpenAI model, Responses, Structured Outputs and Python SDK documentation verified on
  2026-09-20.
- Official Gemini pricing, Structured Outputs, GenerateContent usage metadata and Python SDK
  documentation verified on 2026-09-20.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6801 | Frozen candidate/SDK contract | Worker pins `openai==3.16.2`, `google-genai==2.24.0`; exact model constants and environment example | TC-6801 |
| REQ-6802 | Provider-neutral architecture | `ProviderCandidate`, `ProviderAdapter` implementations under Worker Infrastructure | TC-6802, TC-6809 |
| REQ-6803 | Price before paid call | `execute_priced_candidate()` resolves and retains `ProviderPriceVersion` before adapter execution | TC-6802 |
| REQ-6804 | Structured output and tools disabled | Responses JSON Schema + empty tools; Gemini JSON Schema + no tools/cache + disabled automatic function calling | TC-6803, TC-6805 |
| REQ-6805 | 5s connect/60s total, no SDK retry | Explicit OpenAI `httpx2.Timeout`/`max_retries=0`; Gemini timeout and `attempts=1` total attempt | TC-6801, TC-6806 |
| REQ-6806 | OpenAI cache-write fail-closed | Explicit cache mode; required zero `cache_write_tokens`; stable unsupported-accounting error | TC-6803, TC-6804 |
| REQ-6807 | Gemini token normalization | Prompt/cached/candidate/thinking token mapping and cached-subset validation | TC-6805 |
| REQ-6808 | Safe bounded failures | SDK errors and safety blocks map to Provider-neutral classes without raw error/body propagation | TC-6807 |
| REQ-6809 | No runtime promotion/customer content | No composition-root wiring; ADR Primary/Fallback none; synthetic-only evaluation boundary | TC-6801, TC-6808 |
| REQ-6810 | Documentation and repository gates | ADR/mirror/Worker docs, development/test records and full quality suite | TC-6809 |

## Assumptions and Clarifications

The owner selected the two exact candidates, approved their documented public rates, froze
timeouts/retry/tool/cache behavior, required pre-call pricing and prohibited customer content during
evaluation. The owner also required OpenAI cache-write usage to remain zero or fail closed. ADR-055
does not invent Catalog identity data: controlled provisioning of `pricing_version` and exact
`effective_from` remains required before a paid evaluation.

**Unapproved assumptions:** None

## Changes

- Added the application preflight executor that resolves and retains the exact immutable Price
  Version before invoking an explicitly supplied candidate adapter.
- Added OpenAI Responses and Gemini GenerateContent Infrastructure adapters with exact model
  allowlisting, mandatory JSON Schema output, disabled tools/retries and bounded timeouts.
- Added normalized usage mapping, required count validation, cached-input subset enforcement,
  safety-block mapping and safe Provider-neutral failures.
- Added the OpenAI explicit-cache guard: missing, malformed or non-zero cache-write accounting
  fails closed and cannot produce an authoritative Usage record.
- Pinned both official SDKs and replaced generic Provider placeholders in `.env.example` with empty
  evaluation-only credentials and exact candidate model identifiers.
- Added ADR-055, updated ADR-022, Worker/architecture mirrors and the repository contract suite.

## Architecture and Design Decisions

- Application knows only `ProviderAdapter`, candidate identity, Price Catalog and normalized result;
  SDK imports remain exclusively in Worker Infrastructure.
- No Provider is wired into the Worker composition root, so candidate availability cannot become an
  accidental runtime default.
- Credential/model checks and Price resolution happen before any paid request. Missing Price stops
  execution; no zero-cost or arbitrary-price fallback exists.
- The current three-rate Ledger cannot price OpenAI cache writes. Explicit cache mode plus a strict
  zero assertion prevents silent under-accounting without prematurely changing G06 schema.
- Gemini thinking tokens are included in normalized output tokens, while Context Cache creation is
  absent from the request contract.
- Public price values are documented for evaluation governance but not inserted with invented
  Catalog identity/effective-time data.

## Structure Preservation

- The modular monolith and existing Web/API/Worker deployables are unchanged; no service, public
  endpoint, queue, scheduler, database table or UI was added.
- Domain and shared Application packages import no Provider SDK. Concrete SDK code is contained in
  `apps/worker/app/infrastructure/ai/`.
- The existing provider-neutral result, Routing Policy, Usage Ledger and immutable Price Catalog
  contracts remain intact.
- Runtime routing, fallback, Provider promotion, real-price provisioning and customer-data approval
  remain outside this increment.

## Senior Review

- PASS: both model identifiers and SDK versions exactly match the approved contract.
- PASS: tools, search/function calling, implicit cache writes, Gemini Context Cache and SDK retries
  are disabled explicitly.
- PASS: Price Catalog resolution occurs before the only adapter invocation and the exact resolution
  remains attached to the result.
- PASS: OpenAI cache-write accounting is required and zero; absence or non-zero usage fails closed.
- PASS: Gemini output includes candidates plus thinking tokens and both adapters enforce the
  cached-input subset invariant.
- PASS: safety and SDK failures cross the boundary only as bounded error classes; no raw exception,
  response body, prompt, input, output or secret is logged.
- PASS: no runtime primary/fallback, customer-content path or live paid call was introduced.
- PASS: focused tests and the complete regression, lint, typecheck, build, secret and dependency
  gates passed.

## Verification

See [test-report.md](./test-report.md). Contract-first tests first failed on missing SDKs/adapters,
then the focused suite and full repository regression passed with local PostgreSQL 16. Automated
verification made no external Provider request and used no customer data.

## Remaining Risks

- Model quality is not established by deterministic fakes; a controlled real-Provider run against
  approved synthetic fixtures is still required.
- Paid evaluation remains fail-closed until Platform provisions exact Catalog rows and runtime
  secrets outside source control.
- Gemini prices change on 2027-01-01 and require a new immutable Catalog version before use then.
- Any observed non-zero OpenAI cache-write usage requires an approved G06 Ledger/Catalog expansion,
  not a relaxed assertion.
- Provider promotion, fallback and customer-data use require separate approvals.

**Final status:** PASS
