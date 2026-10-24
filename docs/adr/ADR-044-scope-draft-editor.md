# ADR-044 — S1-K04-A Scope Draft Editor

- **Status:** Accepted
- **Date:** 2026-09-12
- **Owner:** Aria AI Engineering
- **Story:** S1-K04-A
- **Related decisions:** ADR-041 (Scope Draft model), ADR-042 (readiness), ADR-043 (generation)

## Decision

K04-A exposes the current Working Scope Draft through a tenant-authorized read route and permits
explicit, section-at-a-time human edits through a compare-and-swap mutation. Selective AI
regeneration is split into K04-B and remains deferred because Provider, cost guard, Job and
idempotency contracts are not approved.

## Current Draft read contract

`GET /api/v1/projects/{project_id}/scope/draft` resolves only the Draft whose `context_version`
equals the Project's `current_context_version`. Its public response contains only `id`,
`context_version`, `content` and `updated_at` in the standard envelope. A missing Project, deleted
Project, cross-tenant Project, Context Version zero, absent current Draft or historical-only Draft
returns the same safe `404 RESOURCE_NOT_FOUND` response.

## Section mutation contract

`PATCH /api/v1/projects/{project_id}/scope/draft/sections/{section_id}` accepts exactly:

```json
{
  "value": "section-specific JSON value",
  "expected_updated_at": "ISO-8601 timestamp"
}
```

The server locks and resolves the tenant-scoped edit target, rejects a historical Draft with
`409 SCOPE_DRAFT_STALE`, checks `expected_updated_at`, replaces only the target section's `value`,
preserves the target `trace`, validates the complete `scope_content_schema_v1` document and commits
atomically. A CAS mismatch returns `409 VERSION_CONFLICT`. Neither error is retryable without a
fresh user decision.

Structured values use full replacement rather than merge semantics. An omitted existing item is
intentionally removed. Existing `item_id` values are immutable and may only reference IDs already
present in that section. A new item omits `item_id`; the server assigns a UUID. A caller-supplied
unknown ID is rejected. `pages_sections` applies these rules to both page and nested section IDs.

## Lineage and human control

`trace` is server-owned. The public request cannot add, remove or edit it. Preserved trace records
the original derivation lineage and is not presented as semantic proof after a human edit. The UI
labels it accordingly.

The editor exposes all twelve K01 sections, saves only through an explicit user action, retains the
local value after a failed save, warns before dirty section changes or navigation and distinguishes
conflict from stale-Draft states. It shows no fabricated progress, readiness percentage or AI
score. No regeneration control, including disabled or “coming soon” UI, exists in K04-A.

## Authorization and observability

Only an authenticated identity with an active `owner`, `admin` or `member` Membership in the
selected Account may read or mutate the Draft. Authorization is enforced by the API, not by UI
visibility.

Operational events are `scope_draft.section_updated`, `scope_draft.version_conflict`,
`scope_draft.stale_rejected` and `scope_draft.persistence_failed`. They contain safe identifiers,
section/context metadata, status, duration and error code where relevant, never Scope value,
content, trace or customer text. The separate Product Analytics event `scope_edited` contains only
`project_id`, `section_id`, `context_version` and schema metadata.

## Explicit non-decisions

- No section regeneration, Provider, model, prompt, queue, Job, cost guard or retry policy.
- No auto-save, implicit overwrite, historical Draft rebinding or merge-patch behavior.
- No Draft creation endpoint, readiness mutation or new database schema.
- No trace editing or semantic re-validation claim.

## Consequences

Human edits are concurrency-safe, tenant-scoped and structurally valid while K01 remains the single
Draft schema authority. K04-B can later add selective generation only after its independent
contracts are approved.
