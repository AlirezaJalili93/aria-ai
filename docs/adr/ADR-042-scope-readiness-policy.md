# ADR-042: Scope Readiness Policy

- **Status:** Accepted — owner approval received 2026-09-12
- **Story:** S1-K02 — Scope Readiness Policy
- **Extends:** ADR-037 Versioned Gap Completion Checklist and Critical Rule Pack; ADR-039 Gap Inbox Review; ADR-041 Scope Draft Model
- **Supersedes:** persisted `scope_drafts.readiness_status` as the K01/K02 source of truth; readiness is computed and not stored in this increment

## Context

The Sprint 1 Backlog requires `Critical unresolved gap → ready_for_share=false` unless the
human explicitly resolves it. K01 deliberately stores only the mutable Scope Draft and does not
persist readiness. ADR-037 makes the deterministic Critical Rule Pack authoritative, while ADR-039
distinguishes a dismissed Gap from an ignored Clarification.

## Decision

K02 is a pure Domain policy. It receives the current Project Context Version and tenant-scoped Gap
metadata from an Application/Repository caller and returns:

```yaml
ready_for_share: boolean
reason_code: critical_gap_open | no_open_critical_gaps
blocking_gap_ids: UUID[]
```

Only Gaps from the current Context Version are evaluated. Historical Gaps are ignored after
tenant/project validation; evidence from another Account or Project, duplicate evidence IDs, or a
future Context Version fails closed. `context_version` must be at least one.

The blocking predicate is exactly:

```text
status = open
AND severity = critical
AND context_version = Project.current_context_version
```

`resolved` and `dismissed` are both terminal non-blocking outcomes. A dismissed Gap is an explicit
human resolution and K02 does not re-judge that decision. An ignored Clarification does not change
the Gap status and is therefore not treated as a Gap dismissal.

J02 owns Critical Rule Pack evaluation. K02 consumes persisted Gap severity after that deterministic
evaluation and never trusts a raw model Critical signal or re-runs the Rule Pack. No completeness
score, percentage, progress count, content validation, Scope generation, or readiness UI is added.

## Persistence and boundaries

K02 adds no migration, readiness column, public HTTP route, API representation, or snapshot. The
Data Dictionary's older `readiness_status=draft|blocked|ready` field is superseded for this
increment by the computed decision above. K01's `scope_drafts` schema and `updated_at` CAS remain
unchanged.

## Observability

If an Application caller instruments evaluation, only `account_id`, `project_id`,
`context_version`, `blocking_gap_count`, `reason_code`, correlation metadata and duration are
allowed. Scope content, Gap explanation, source references, Context/Requirement text and raw
signals are prohibited.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-K02; synchronized 2026-09-12
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Scope and Gap baseline; synchronized 2026-09-12
- [ADR-037](./ADR-037-gap-critical-rule-pack.md) — authoritative Critical Rule Pack
- [ADR-039](./ADR-039-gap-inbox-review-contract.md) — Gap dismissal and Clarification distinction
- [ADR-041](./ADR-041-scope-draft-model.md) — K01 persistence boundary
- Owner-approved K02 refinement dated 2026-09-12: dismissed Gap is explicit human resolution and non-blocking.
