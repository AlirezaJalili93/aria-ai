# Development Record: 0054 — Scope Draft Model

- **Status:** COMPLETE
- **Increment:** S1-K01
- **Source sync date:** 2026-09-12
- **Completed:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Implement the approved K01 Scope Draft Domain, strict `scope_content_schema_v1` JSONB
validation, tenant-safe persistence and Application/Repository boundary. The Draft is mutable,
unique per Project/Context Version, uses `updated_at` CAS, and becomes historical/read-only when
the Project advances its current Context Version. Readiness, public API/UI, AI generation,
immutable snapshots and snapshot hashing remain outside K01.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K01; synchronized 2026-09-12
- Repository `docs/architecture/data-model.md` — Scope Draft baseline
- Repository `docs/architecture/system-architecture.md` — Scope boundary and immutable versions
- [ADR-041](../../adr/ADR-041-scope-draft-model.md)
- Owner-approved K01 refinements dated 2026-09-12

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-5401 | K01; Data Dictionary | `scope_drafts` migration/model | TC-5401, TC-5402 |
| REQ-5402 | K01 frozen content contract | `scope_draft.py` strict schema validator | TC-5403, TC-5404 |
| REQ-5403 | K01 cardinality/lifecycle | unique Project/Context Version and historical update guard | TC-5405, TC-5406 |
| REQ-5404 | K01 traceability | Repository same-tenant/context target validation | TC-5407, TC-5408 |
| REQ-5405 | K01 CAS/actor contract | Repository update boundary and actor checks | TC-5409, TC-5410 |
| REQ-5406 | K01 persistence security | restrictive FKs, RLS, indexes and denied Data API access | TC-5401, TC-5411 |
| REQ-5407 | K01 safe observability | ADR and content-safe contract tests | TC-5412 |
| REQ-5408 | K01 scope boundary | ADR, module boundary and no HTTP/readiness/snapshot code | TC-5413 |

## Changes

- Added `0017_scope_drafts` with strict JSONB object, actor checks, tenant composite FK,
  restrictive deletes, unique `(project_id, context_version)`, timestamps, RLS and fail-closed
  Data API grants.
- Added Scope Draft Domain objects and strict validation for all twelve canonical sections,
  structured nested item IDs, trace ordering/uniqueness and actor invariants.
- Added tenant/context-aware Repository and Unit of Work ports; create validates Project Context
  bounds and trace targets, while update enforces historical protection and `updated_at` CAS.
- Added ADR-041, architecture mirror updates, migration documentation and Contract tests.

## Structure Preservation

- Scope code remains isolated under `apps/api/app/modules/scope/{domain,application,infrastructure}`.
- No public route, Web UI, readiness state, revision column, AI provider, worker task, snapshot or
  hash policy was added.
- Existing modular-monolith, Alembic, RLS and tenant-first repository boundaries are preserved.

## Senior Review

**Status:** PASS.

- Confirmed all twelve sections are structurally required while empty values remain valid in K01.
- Confirmed Scope values contain editable content and trace contains lineage IDs only.
- Confirmed user/AI/system actor semantics and user actor requirement.
- Confirmed cross-row Context upper-bound validation remains Application/Repository logic; no
  unsafe PostgreSQL CHECK or trigger was introduced.
- Confirmed historical Draft mutation is blocked after Context advancement.
- Confirmed readiness, public API/UI, AI generation and immutable Snapshot remain deferred.

## Verification

See [test-report.md](./test-report.md). Verification includes K01 Contract tests, full API tests
with PostgreSQL migrations through `0017_scope_drafts`, lint, typecheck, architecture validation,
secret scan and diff hygiene.

## Remaining Risks

- K02 still owns Scope Readiness and business completeness of empty sections.
- K03 owns AI-generated Draft orchestration and Usage Ledger integration.
- K04 owns public Draft API/UI and external mutation/idempotency transport contract.
- K05 owns immutable Scope Version snapshots and hash algorithm.

## Assumptions and Clarifications

- No unapproved assumptions were introduced. K01 follows the owner-approved contract; unresolved
  readiness, generation, public API/UI, snapshot and hash decisions remain explicitly deferred to
  K02-K05.

**Unapproved assumptions:** None
