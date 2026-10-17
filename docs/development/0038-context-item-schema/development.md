# Development Record: 0038 Context Item Schema

- Increment ID: `0038-context-item-schema`
- Date: 2026-09-05
- Story: S1-H01 — Context Item Schema
- [Test report](./test-report.md)

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H01; Drive modified 2026-08-17, reviewed 2026-09-05
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Drive modified 2026-09-01, reviewed 2026-09-05
- [Production Data Architecture & Database Schema v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — Drive modified 2026-08-17, reviewed 2026-09-05
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — Drive modified 2026-08-17, reviewed 2026-09-05
- Owner-approved canonical H01 contract dated 2026-09-05

Repository documents are developer-facing mirrors. The linked approved Drive documents and the
explicit owner resolution above are canonical.

## Scope

Create the logical M004 Context Item schema, Domain model and provider-neutral persistence boundary.
Validate each JSON provenance reference against an existing ready same-tenant Source Version before
persisting. Record the supersede of older Context Item fields without implementing H02, API, UI,
content normalization or a new Context Version table.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3801 | H01 exact fields/vocabularies/version/default — owner contract; Backlog; Data Dictionary | `0008_context_items.py`; `context_item.py`; `models.py` | TC-3801, TC-3802, TC-3803 |
| REQ-3802 | Source Reference shape and half-open offsets — owner contract | `SourceReference`; `CreateContextItemUseCase` | TC-3804, TC-3805 |
| REQ-3803 | Semantic provenance validation — owner contract; AI Workflow | Context Item port/use case/SQLAlchemy repository | TC-3805, TC-3806 |
| REQ-3804 | Confirmed Fact evidence rule — owner contract; AI Workflow AI-01 | Domain, Application validation and DB checks | TC-3803, TC-3805 |
| REQ-3805 | Creator semantics — owner contract | Domain and DB creator checks; Profile FK RESTRICT | TC-3803, TC-3807 |
| REQ-3806 | Tenant/history/security baseline — owner contract; architecture baseline | Composite tenant FK; RESTRICT FKs; indexes; RLS/revokes | TC-3801, TC-3807, TC-3808 |
| REQ-3807 | No content logging or deferred surfaces — owner contract | No logger or router introduced; ADR-025 | TC-3809 |

## Assumptions and Clarifications

The owner explicitly resolved the document conflicts on 2026-09-05: integer `context_version`,
plural `source_refs`, the four-state status vocabulary, exact Source Reference semantics and all
three restrictive parent FK actions are canonical. Content policy, API/UI, H02 and a physical
Context Version entity remain deferred.

**Unapproved assumptions:** None

## Changes

- Added Alembic revision `0008_context_items` with exact fields, checks, tenant-first indexes,
  restrictive foreign keys, RLS and explicit Data API revokes.
- Added pure Domain Context Item and Source Reference types with exact vocabulary and offset
  invariants while preserving content verbatim.
- Added an Application Unit of Work and create use case that resolves every provenance target
  before the repository insert and commits once.
- Added a SQLAlchemy adapter that only resolves matching ready Source Versions in the same Account
  and Project, validates canonical text bounds, serializes exact Source References and maps the
  persisted row back to Domain.
- Added ADR-025 and synchronized data-model/migration mirrors.

## Architecture and Design Decisions

- `context_version` remains an integer and no `context_versions` entity is introduced.
- JSONB stores the approved Source Reference value objects; operational Source and Version rows
  remain normalized entities and authoritative provenance targets.
- The composite Project/Account foreign key preserves tenant consistency at the database boundary.
- Semantic JSON reference validation remains Application/Repository behavior because PostgreSQL
  cannot express element-level JSONB foreign keys.
- No structured event is emitted in H01, so Context content and Source References cannot leak into
  logs through this increment.

## Structure Preservation

- Existing Web/API/Worker deployables and modular-monolith boundaries are unchanged.
- Domain imports no framework, persistence, observability or Provider code.
- Application depends only on its repository/Unit-of-Work port; SQLAlchemy is isolated under
  Infrastructure.
- Migration ownership remains Alembic under ADR-008; logical M004 is delivered as physical 0008
  without rewriting earlier applied revisions.
- OpenAPI and UI are unchanged, and H02/G02/G03/G06 remain deferred.

## Senior Review

- PASS: fields, numeric precision, defaults and vocabularies match the owner-approved canonical
  contract; no content length or normalization policy was introduced.
- PASS: the Domain value object enforces paired half-open offsets, user creator consistency and the
  confirmed-Fact evidence precondition without importing framework or Infrastructure code.
- PASS: the Application validates every Source/Version identity, tenant, ready state and canonical
  text bound inside the same Unit of Work before inserting and committing once.
- PASS: the SQLAlchemy resolver cannot accept missing, cross-tenant, mismatched or non-ready Source
  Versions; exact Source Reference JSON is persisted only after validation.
- PASS: PostgreSQL checks reject invalid JSON shape, vocabulary, confidence and shallow evidence;
  the guarded `CASE` avoids unsafe array-length evaluation for non-array JSON.
- PASS: Account/Project/Profile history uses indexed `ON DELETE RESTRICT` links, Project identity is
  tenant-consistent, RLS is enabled and Data API roles hold no direct privilege.
- PASS: no API/router, UI, Context Version table, Provider behavior or content-bearing log event was
  added. Full tests, lint, typecheck, builds and architecture validation passed.

## Verification

See [test-report.md](./test-report.md). Focused contract/Domain/Application/PostgreSQL verification
and the final repository-wide quality gates passed.

## Remaining Risks

- JSONB Source References require all future write paths to use the validated Application boundary;
  direct owner-level SQL can bypass semantic reference checks.
- H02 must define the workflow that produces proposed Context Items before this schema is exposed.
- Content length/normalization and a Context Version entity remain intentionally unresolved.

**Final status:** PASS
