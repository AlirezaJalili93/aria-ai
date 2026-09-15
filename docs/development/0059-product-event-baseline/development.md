# Development Record: 0059 — Product Event Baseline

- **Status:** COMPLETE
- **Increment:** S1-L01
- **Source sync date:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Implement the approved, provider-neutral Product Analytics baseline for server-owned outcome
events and separate client-owned interaction events. The increment freezes the event envelope,
per-event property allowlists, deterministic event IDs, process-level duplicate suppression,
transaction-aware emission points, negative leakage tests and the contract schema. No analytics
provider, database table, deployable service or unrelated domain behavior is added.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L01; synchronized 2026-09-12
- [System Architecture v2](../../architecture/system-architecture.md) — modular monolith and observability boundaries; synchronized 2026-09-12
- [Product Analytics Baseline approval](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — owner-approved refinements dated 2026-09-12
- [ADR-046](../../adr/ADR-046-product-analytics-baseline.md) — canonical L01 contract

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-5901 | L01 envelope contract | `product_analytics.py`, `product-analytics.schema.json`, web emitter | TC-5901, TC-5902 |
| REQ-5902 | L01 server-owned outcome vocabulary | API/Application instrumentation at commit boundaries | TC-5903, TC-5904 |
| REQ-5903 | L01 per-event allowlists and safe enums | `ProductAnalyticsEvent` validation and schema vocabulary | TC-5905, TC-5906 |
| REQ-5904 | L01 stable event ID and idempotent replay | UUID5 helper and `StructuredEventLogger` dedup set | TC-5907, TC-5908 |
| REQ-5905 | L01 event cardinality rules | one event per persisted Gap/batch/Draft/version | TC-5909 |
| REQ-5906 | L01 client interaction separation | web interaction union and nullable pre-project context | TC-5910 |
| REQ-5907 | L01 transactional consistency | outcome emission follows successful persistence commits | TC-5911 |
| REQ-5908 | L01 negative leakage gate | allowlist and static/content-safe tests | TC-5912, TC-5913 |

## Assumptions and Clarifications

- The owner-approved refinement permits the pre-project `project_type_selected` client interaction
  to serialize `project_id: null`; no server outcome uses a nullable project ID.
- Existing operational logging remains separate from Product Analytics; the new helper is the only
  product-event construction boundary.
- Stable IDs provide the ingestion idempotency key; no provider or persistent analytics store is
  introduced before a separately approved decision.

**Unapproved assumptions:** None

## Changes

- Added a typed Python Product Analytics contract with fixed envelope, allowlists, enum checks and
  deterministic UUID5 IDs.
- Added structured logger emission with duplicate event-ID suppression and safe UUID serialization.
- Instrumented project, context, structuring, requirement, gap, scope and scope-version outcomes
  without content-bearing fields.
- Replaced ad-hoc web product event logging with separate interaction names and versioned envelope.
- Added the versioned JSON contract, contract tests, API tests and ADR-046.

## Structure Preservation

- Domain and Application remain provider/framework neutral; analytics is an observability port.
- Existing operational event names, transactional persistence and tenant-scoped identifiers remain
  unchanged; Product Analytics is emitted only at the approved boundaries.
- No new provider, queue, database table, API endpoint or deployable service was introduced.
- Existing UI RTL/token/accessibility structure and existing API/Worker layering were preserved.

## Senior Review

**Status:** PASS.

- Corrected import ordering and strict typing after the first lint/typecheck pass.
- Ensured logger test doubles remain compatible through the generic structured `emit` fallback while
  the canonical logger emits the exact Product Analytics envelope.
- Verified duplicate IDs are suppressed, unknown properties and unsafe enum values fail closed, and
  static tests reject provider coupling and content leakage.
- Verified existing API/Web behavior and K05 contract tests remain green after instrumentation.

## Verification

Focused contract, API and Web tests passed. Full lint, typecheck, build, architecture validation,
secret scan and complete test suite passed; command evidence is recorded in
[test-report.md](./test-report.md).

## Remaining Risks

- Durable downstream ingestion and warehouse delivery are intentionally deferred until an approved
  analytics provider/retention contract exists.
- Client interaction events currently use console-based structured emission; transport integration
  remains outside L01.
- Hosted provider quality or analytics dashboard evidence is not part of this increment.
