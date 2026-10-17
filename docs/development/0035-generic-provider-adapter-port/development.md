# Development Record: 0035 Generic Provider Adapter Port

[Test report](./test-report.md)

## Scope

- Increment ID: `0035-generic-provider-adapter-port`
- Stories: `S1-G01` follow-up boundary; `S1-G02/G03` concrete adapters explicitly deferred
- Status: Completed
- Scope: generic provider-neutral `ProviderAdapter` port and normalized `ProviderResult`.
- Explicitly deferred: Provider selection, concrete adapters, SDKs, model names, credentials,
  endpoints, timeout values, retry counts, routing, fallback and Usage Ledger writes.

## Source Documents

- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk) — adapter responsibilities and normalized fields; read 2026-09-05.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — G02/G03 Provider Adapter stories; read 2026-09-05.
- [ADR-021 — Provider-Neutral AI Execution Port](../../adr/ADR-021-ai-execution-port.md)
- [ADR-022 — Generic Provider Adapter Port](../../adr/ADR-022-generic-provider-adapter-port.md)
- Repository `AGENTS.md`

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3501 | Owner approval 2026-09-05; AI Workflow Specification | Generic async `ProviderAdapter.execute(request)` port | TC-3501 |
| REQ-3502 | Owner approval; AI Workflow Specification | Normalized `ProviderResult` with approved minimum fields | TC-3502 |
| REQ-3503 | AI Workflow Specification §20; ADR-021 | Provider-neutral mapped error with explicit retryability | TC-3503 |
| REQ-3504 | Owner approval; Architecture v2 | No Provider SDK/name/model/credential/endpoint enters Application | TC-3501, TC-3504 |
| REQ-3505 | Owner approval; ADR-022 | G02/G03 remain Deferred/Blocked pending Provider Selection Decision and Evaluation Gate | TC-3504 |

## Changes

- Added generic Application `ProviderAdapter` Protocol with an opaque structured request.
- Added normalized `ProviderResult` for the approved minimum response fields.
- Added provider-neutral mapped adapter error with the existing AI error taxonomy.
- Added ADR-022, unit tests and repository contract tests.
- Updated ADR-021 to reference the generic adapter boundary.

## Structure Preservation

- The port remains provider-neutral in Worker Application; no Infrastructure provider code was
  added.
- No endpoint, SDK, model, secret, timeout, retry, routing or metering behavior was introduced.
- `AIExecutionPort` remains the Application orchestration boundary; the generic adapter port is a
  downstream seam only.
- G02/G03 are explicitly recorded as Deferred/Blocked, not reported as implemented.

## Senior Review

- PASS: generic `ProviderAdapter.execute(request)` is the only adapter boundary added.
- PASS: normalized result fields match the owner-approved minimum without provider-specific fields.
- PASS: standardized errors retain explicit retryability and raw SDK errors cannot cross the port.
- PASS: no Provider, SDK, model, secret, endpoint, timeout or retry value was invented.
- PASS: G02/G03 remain explicitly Deferred/Blocked and are not reported as implemented.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The owner explicitly approved a generic adapter port and deferred concrete Provider selection on
2026-09-05. No Provider-specific behavior is inferred.

## Verification

See [test-report.md](./test-report.md). Focused tests and all repository gates passed.

## Remaining Risks

- G02/G03 cannot start until Provider Selection, SDK, model, credential and evaluation decisions are
  approved.
- A concrete adapter must preserve the normalized result and error taxonomy without leaking raw SDK
  errors.
- AI production readiness remains blocked until adapter integration, usage metering, validation,
  retry/fallback and eval gates are complete.

**Final status:** PASS
