# Development Record: 0057 — Scope Draft Editor

- **Status:** COMPLETE
- **Increment:** S1-K04-A
- **Source sync date:** 2026-09-12
- **Completed:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Expose and edit the current tenant-scoped Scope Draft through a section-at-a-time API and an
RTL-first Web editor. Mutations use `updated_at` compare-and-swap, preserve server-owned lineage,
replace the complete target value atomically and assign server IDs to new structured items.
Selective AI regeneration (K04-B) remains absent.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K04; synchronized 2026-09-12
- [Canonical API Contract](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Scope Draft surfaces; synchronized 2026-09-12
- [Frontend UX State](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — explicit save, unsaved and conflict states; synchronized 2026-09-12
- [Access Control Matrix](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership authorization; synchronized 2026-09-12
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-07-02 human section editing; synchronized 2026-09-12
- Owner-approved K04-A refinement dated 2026-09-12
- [ADR-041](../../adr/ADR-041-scope-draft-model.md), [ADR-042](../../adr/ADR-042-scope-readiness-policy.md), [ADR-043](../../adr/ADR-043-scope-generation-use-case.md), [ADR-044](../../adr/ADR-044-scope-draft-editor.md)

Drive documents remain canonical; this record mirrors their approved K04-A implementation scope.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-5701 | K04-A current-Draft read | `GET /projects/{project_id}/scope/draft`; tenant/current join | TC-5701, TC-5702 |
| REQ-5702 | Section-only full replacement | `replace_scope_section_value`; PATCH route and service | TC-5703, TC-5704 |
| REQ-5703 | Server-owned lineage and IDs | trace-preserving Domain function; unknown-ID rejection | TC-5704, TC-5705 |
| REQ-5704 | Optimistic concurrency and stale separation | DB trigger CAS; `VERSION_CONFLICT`; `SCOPE_DRAFT_STALE` | TC-5706, TC-5707 |
| REQ-5705 | Active tenant authorization and safe 404 | Tenant dependency; account/project-scoped repository queries | TC-5702, TC-5708 |
| REQ-5706 | Explicit-save RTL editor | `/projects/{projectId}/scope`; twelve section editors | TC-5709, TC-5710 |
| REQ-5707 | Failure-safe human control | local dirty state, navigation guard, retained value, conflict/stale UI | TC-5710 |
| REQ-5708 | Safe observability and analytics | approved operational events; content-free `scope_edited` | TC-5711 |
| REQ-5709 | K04-B exclusion | no Provider, Job, cost guard, regenerate command or control | TC-5712 |

## Changes

- Added a tenant-scoped Scope Draft Application service and SQLAlchemy read/edit-target queries.
- Added exact current-Draft GET and section PATCH routes plus stable stale-Draft error mapping.
- Added Domain replacement logic for all K01 value shapes, including nested page/section IDs.
- Extended OpenAPI with exact K04-A request, response and error surfaces.
- Added the twelve-section, accessible RTL editor, explicit saves, local failure retention and dirty
  navigation protection.
- Added product analytics and operational logging that never records Scope content or trace.
- Added unit, API, Web contract and real PostgreSQL integration tests.

## Structure Preservation

- The K01 `scope_content_schema_v1` and existing `scope_drafts` table remain authoritative; no new
  schema, service or alternate Draft representation was introduced.
- Domain replacement code imports only standard-library types. FastAPI and SQLAlchemy remain in
  API and Infrastructure layers respectively.
- Tenant authorization remains the shared `require_tenant_context` dependency and repository
  queries include both `account_id` and `project_id`.
- Web styling uses existing primitive/semantic/component tokens from `design-system/MASTER.md`, is
  RTL-first, retains visible focus behavior and minimum control targets.
- K02 readiness remains computed; K03 generation remains create-only; K04-B regeneration remains
  deferred and absent from API, Application and UI.

## Senior Review

**Status:** PASS.

- Corrected the cross-section CAS flow so every successful save updates the shared Draft timestamp;
  a subsequent section save no longer uses stale state.
- Corrected discarded dirty changes so a confirmed section switch restores the last saved value.
- Hardened the Web adapter to validate the complete envelope, twelve canonical sections, exact
  object shapes, ordered trace IDs and section-specific values before rendering.
- Verified full replacement retains only known client IDs, generates UUIDs for new items, removes
  omitted items and never accepts client lineage.
- Verified historical Drafts are readable only through future explicit history surfaces and cannot
  be rebound or mutated by K04-A.
- Confirmed logs and analytics contain identifiers/metadata only; no Draft value, trace or customer
  text is emitted.

## Verification

Final execution evidence is recorded in [test-report.md](./test-report.md), including the complete
repository gates, production build and real PostgreSQL test.

## Remaining Risks

- K04-B selective AI regeneration remains blocked on its independent Provider, cost, Job,
  idempotency and comparison contracts.
- Browser interaction against a hosted authenticated environment remains deployment evidence, not
  part of this repository-only increment.
- Existing repository-local pytest cache directories produce non-functional Windows permission
  warnings; execution and result integrity are unaffected.

## Assumptions and Clarifications

- The owner-approved K04-A refinement explicitly freezes endpoint shapes, replacement semantics,
  error codes, ID ownership, trace ownership, UX states, event names and K04-B exclusion.
- No undocumented behavior, field, default, limit, Provider or acceptance criterion was added.

**Unapproved assumptions:** None
