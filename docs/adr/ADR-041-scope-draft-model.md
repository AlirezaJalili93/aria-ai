# ADR-041: Scope Draft Model

- **Status:** Accepted — owner approval received 2026-09-12
- **Story:** S1-K01 — Scope Draft Model
- **Supersedes/defers:** persisted `readiness_status` and `revision` on `scope_drafts` are superseded/deferred for K01; readiness belongs to K02 and `updated_at` CAS is canonical concurrency control.

## Decision

K01 stores one mutable Working Draft per `(project_id, context_version)` in strict,
versioned `scope_content_schema_v1` JSONB. All twelve canonical sections must be present,
but empty values are structurally valid. Scope values contain editable Scope content;
`trace` contains only deterministic lineage IDs. A Draft bound to an older Context Version
is historical and read-only. K01 does not calculate readiness, expose public HTTP routes,
create immutable snapshots, or run AI generation.

## Persistence

`scope_drafts` contains `id`, `account_id`, `project_id`, `context_version`, `content`,
`updated_by_type`, `updated_by`, `created_at` and `updated_at`. The database enforces
`context_version >= 1`, JSON object content, actor vocabulary, user actor presence,
tenant composite FK, restrictive deletes and `UNIQUE(project_id, context_version)`.
The upper bound against the Project's current Context Version is an Application/Repository
validation; no cross-row CHECK or trigger is introduced.

## Content contract

The twelve section IDs are `summary`, `goals`, `pages_sections`, `requirements`, `content`,
`visual_direction`, `constraints`, `assumptions`, `resolved_gaps`,
`remaining_non_blocking_gaps`, `out_of_scope` and `acceptance_notes`. Structured nested
items have stable unique `item_id` values. Trace arrays are set-like, duplicate-free,
sorted and tenant/Project/Context-Version validated. Unknown schema versions, sections,
duplicate trace IDs and invalid nested shapes fail validation.

## Mutation and observability

Updates use `expected_updated_at`; mismatch is a version conflict. `updated_by_type` is
`user|ai|system`; a user update requires `updated_by`, while AI/system may use NULL.
Operational events are safe (`scope_draft.created`, `scope_draft.updated`,
`scope_draft.version_conflict`, `scope_draft.persistence_failed`) and never contain
content, section values, customer text or raw trace payloads.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K01; synchronized 2026-09-12.
- Repository Data Model: `docs/architecture/data-model.md` — `scope_drafts` baseline.
- Owner-approved K01 contract refinements dated 2026-09-12.
