# Development Record: 0056 — Scope Generation Use Case

- **Status:** COMPLETE
- **Increment:** S1-K03
- **Source sync date:** 2026-09-12
- **Completed:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Implement the approved K03 provider-neutral Scope Generation Application boundary. It resolves an
exact ready Context Version, accepts only draft/confirmed Requirements, maps AI-05 into the twelve
K01 sections, meters every AI/repair call and creates only a new Scope Draft. No public API,
concrete Provider, worker runtime, migration, readiness persistence or implicit regeneration is
added.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K03; synchronized 2026-09-12
- [AI Workflow Specification](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-05 Scope Draft Generation; synchronized 2026-09-12
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Requirement and Scope baseline; synchronized 2026-09-12
- [ADR-021](../../adr/ADR-021-ai-execution-port.md) — provider-neutral AI execution
- [ADR-024](../../adr/ADR-024-usage-ledger-and-worker-role.md) — append-only Usage Ledger
- [ADR-041](../../adr/ADR-041-scope-draft-model.md) — K01 Draft model and schema
- [ADR-042](../../adr/ADR-042-scope-readiness-policy.md) — K02 computed readiness
- [ADR-043](../../adr/ADR-043-scope-generation-use-case.md) — K03 canonical decision

Drive documents remain canonical; repository mirrors record the source links and sync date above.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-5601 | K03 exact tenant/context snapshot | `ScopeGenerationSnapshotReader.resolve_exact` and snapshot invariants | TC-5601 |
| REQ-5602 | K03 input statuses | `ScopeGenerationRequirement` accepts only `draft`/`confirmed` | TC-5601, TC-5607 |
| REQ-5603 | K02 readiness precondition | `ScopeGenerationBlockedError` before AI | TC-5603 |
| REQ-5604 | AI-05/K01 mapping | `scope_content_schema_v1` validator port and ADR-043 mapping | TC-5606 |
| REQ-5605 | K03 conflict-by-default | pre-AI `exists` check and writer race boundary | TC-5602 |
| REQ-5606 | AI usage contract | `_execute_and_meter` appends every invocation | TC-5604 |
| REQ-5607 | Provider-neutral architecture | injected AI/validator/writer/ledger/logger ports | TC-5606 |
| REQ-5608 | Safe lifecycle logging | started/completed/failed metadata-only events | TC-5606 |

## Changes

- Added `ScopeGenerationUseCase` and provider-neutral command, snapshot, repair and error
  contracts under `packages/backend-application`.
- Added exact status/version/tenant checks, readiness blocking and existing-Draft conflict behavior.
- Added bounded validation repair and Usage Ledger metering for initial and repair calls.
- Added five Application tests and four contract tests using synthetic data.
- Added ADR-043 and updated module/data-model mirrors without adding schema or public surfaces.

## Structure Preservation

- Application imports only existing Application ports and standard-library types; no Provider SDK,
  FastAPI, SQLAlchemy, Celery or Redis dependency was introduced.
- K01 remains authoritative for the twelve-section `scope_content_schema_v1` shape and persistence.
- K02 remains a computed policy; no readiness column or duplicated readiness state was added.
- No API/UI, migration, queue, Provider, regeneration, or result-mapping table was added.

## Senior Review

**Status:** PASS.

- Requirements are limited to `draft` and `confirmed` at the exact target Context Version.
- A blocked K02 snapshot or existing Draft prevents all AI calls and writes.
- Pages and Sections remain a structural nested mapping in `pages_sections`, not free text.
- Initial and repair calls are metered; safe events never contain content or raw Provider material.
- Provider selection, API/Worker wiring and explicit regeneration remain deferred as required.

## Verification

The final repository gates are recorded in [test-report.md](./test-report.md): full npm test,
lint/typecheck, architecture validation, secret scan and diff hygiene.

## Remaining Risks

- Real Provider selection and quality evaluation remain deferred to G02/G03 and approved Eval work.
- Worker/job orchestration and public HTTP wiring remain separate increments.
- Explicit regeneration and immutable historical result replay require a future approved contract.

## Assumptions and Clarifications

- No behavior, field, provider, default, limit, or acceptance criterion outside the approved K03
  contract was introduced.

**Unapproved assumptions:** None
