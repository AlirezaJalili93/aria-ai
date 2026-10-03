# ADR-043 — S1-K03 Scope Generation Use Case

- **Status:** Accepted
- **Date:** 2026-09-12
- **Owner:** Aria AI Engineering
- **Story:** S1-K03
- **Related decisions:** ADR-021 (provider-neutral AI execution), ADR-024 (usage ledger), ADR-041 (Scope Draft model), ADR-042 (Scope readiness policy)

## Decision

K03 adds a provider-neutral Application use case that creates one new Working Scope Draft for an exact `(account_id, project_id, context_version)` snapshot. It uses the existing `AIExecutionPort`, validates the returned `scope_content_schema_v1` candidate through an injected K01 validator, appends one Usage Ledger record for every AI invocation, and persists only a new Draft through an injected writer.

This increment does not add an HTTP route, a worker runtime, a concrete Provider adapter, a migration, a readiness column, a Scope Snapshot, or a regeneration command.

## Input contract

The use case resolves a tenant-scoped, exact Context Version snapshot. Requirements are eligible only when all of the following hold:

```text
project_id = target project
context_version = target context_version
status IN (draft, confirmed)
```

`removed` and `superseded` Requirements are excluded. Context readiness is represented by the K02 computed policy; a snapshot with `ready_for_share = false` is rejected before any AI call. The use case does not infer or invent missing Context, Requirements, Gap data, routing, task type, versions, budgets, or timeouts.

## AI-05 to K01 mapping

The AI-05 conceptual output is structurally mapped into the twelve canonical K01 sections. There is no thirteenth persisted section:

| AI-05 output | K01 section |
| --- | --- |
| Project Overview | `summary` |
| Goals | `goals` |
| Pages + Sections | `pages_sections` |
| Functional Requirements | `requirements` |
| Content Requirements | `content` |
| Visual Direction | `visual_direction` |
| Constraints | `constraints` |
| Assumptions | `assumptions` |
| Resolved Gaps | `resolved_gaps` |
| Remaining Non-blocking Gaps | `remaining_non_blocking_gaps` |
| Out of Scope | `out_of_scope` |
| Acceptance Notes | `acceptance_notes` |

Pages and Sections are merged as nested structural records inside `pages_sections`; free-form text concatenation is not a contract. K01 remains the authority for exact section shape, trace fields, and schema validation.

## Draft conflict and regeneration boundary

Before executing AI, the use case checks for an existing Draft at the same `(project_id, context_version)` within the tenant. If one exists, it returns `SCOPE_DRAFT_ALREADY_EXISTS` with `retryable = false`; no AI call and no persistence occur. The write boundary must also reject a concurrent race with the same conflict.

K03 never silently overwrites a Draft. Regeneration is a separate, explicit use case and remains deferred until its lineage, human-edit protection, and replacement semantics are approved. K03 does not create a result-mapping table or an immutable historical payload snapshot.

## Repair and metering

Repair policy is explicit and versioned. Sprint 1 permits zero or one repair. A validation failure may invoke the repair prompt only when the command's policy allows it. Every initial or repair AI invocation is appended to the Usage Ledger, including failed execution responses, before a non-success response is surfaced as a safe Application error. Provider SDK types and provider names do not enter Domain/Application code.

## Observability and safety

The use case emits `scope.generation_started`, `scope.generation_completed`, and `scope.generation_failed` with safe IDs, versions, status, repair number, duration, and reason code. Logs must never contain Context text, Requirement or Gap content, source references, prompt text, or a raw Provider response.

## Explicit non-decisions

- No concrete Provider, model, SDK, API key, queue, scheduler, or retry transport is selected.
- No public API/UI or frontend redirect is added.
- No readiness state is persisted; K02 remains a computed policy.
- No implicit default Tier, task vocabulary, timeout, budget, or regeneration behavior is introduced.

## Consequences

K03 can be contract-tested with a deterministic Fake Provider and can be connected to a Worker later without changing the Application boundary. A real AI quality gate remains blocked on the approved provider selection (G02/G03) and the separate evaluation contract.
