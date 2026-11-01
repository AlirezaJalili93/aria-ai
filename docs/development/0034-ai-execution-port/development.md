# Development Record: 0034 Provider-Neutral AI Execution Port

[Test report](./test-report.md)

## Scope

- Increment ID: `0034-ai-execution-port`
- Story: `S1-G01 — Provider-neutral Gateway Interface`
- Status: Completed
- Scope: Worker Application `AIExecutionPort`, standardized structured response and provider error
  taxonomy from the approved AI Workflow Specification.
- Explicitly deferred: provider adapters, routing implementation, fallback execution, retry/backoff
  runtime, schema/business validation, Usage persistence, pricing, prompts and AI eval execution.

## Source Documents

- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk) — canonical AIExecutionPort, response, errors and provider boundary; read 2026-09-05.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-G01 scope and ordering; read 2026-09-05.
- [Repository & Code Structure Specification v1.0](https://docs.google.com/document/d/1NkMTAZRTIgyqfd1C4pKVRRK69swPQI7T-YymV9hBzz0/edit?usp=drivesdk) — AI boundary placement and dependency rules; read 2026-09-05.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit?usp=drivesdk) — Usage Record field vocabulary; read 2026-09-05.
- [ADR-021 — Provider-Neutral AI Execution Port](../../adr/ADR-021-ai-execution-port.md)
- Repository `AGENTS.md`

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3401 | AI Workflow Specification §4; S1-G01 | Async provider-neutral `AIExecutionPort.execute_structured` with the canonical parameters | TC-3401 |
| REQ-3402 | AI Workflow Specification §4; Data Dictionary usage vocabulary | `StructuredAIResponse` with the approved execution and version fields | TC-3402 |
| REQ-3403 | AI Workflow Specification §20 | Bounded standardized provider error classes | TC-3403 |
| REQ-3404 | AI Workflow Specification §§2, 5, 20; Architecture v2 | Application contains no provider SDK/types and keeps input context provider-neutral | TC-3401, TC-3404 |
| REQ-3405 | AI Workflow Specification §§20–22 | Retryability is explicit; adapter, retry and fallback behavior remain separate boundaries | TC-3403, TC-3404 |

## Changes

- Added Worker Application `AIExecutionPort` with the canonical structured execution signature.
- Added `StructuredAIResponse` containing only approved response metadata.
- Added `AIExecutionError` with the approved error taxonomy and explicit retryability.
- Added ADR-021, Python unit tests and repository contract tests.
- Kept provider adapters, routing, retry/fallback, validation and metering outside this increment.

## Structure Preservation

- AI contract remains in Worker Application and imports no provider SDK, Queue client, Redis or
  persistence adapter.
- Provider-specific translation remains reserved for Infrastructure adapters.
- No new provider, secret, migration, deployable, prompt or Usage Ledger write was introduced.
- Existing parser, Jobs, Outbox and tenant boundaries remain unchanged.

## Senior Review

- PASS: Application exposes the exact canonical `execute_structured` parameter boundary.
- PASS: standardized response contains only the approved execution metadata and version fields.
- PASS: provider failures use the approved bounded taxonomy and explicit retryability.
- PASS: no provider SDK, adapter, routing, fallback, retry runtime, validation or Usage persistence
  was invented.
- PASS: structured output remains an untrusted candidate and downstream validation remains explicit.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The canonical AI Workflow Specification supplies the complete G01 port and error vocabulary. Detail
that belongs to G02–G06 remains explicitly deferred.

## Verification

See [test-report.md](./test-report.md). Focused tests and all repository gates passed.

## Remaining Risks

- Provider adapters must map raw SDK failures to the approved error classes without leaking raw
  provider errors.
- Retry/fallback ownership and routing behavior require their later stories and must not be inferred
  from this port.
- Usage persistence and price versioning remain required before any AI workflow is production-ready.

**Final status:** PASS
