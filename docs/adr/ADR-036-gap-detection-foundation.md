# ADR-036: Gap Detection Foundation

- **Status:** Accepted for S1-J02-A — owner approval received 2026-09-09
- **Date:** 2026-09-09
- **Story:** S1-J02-A — Gap Detection Foundation
- **Extends:** ADR-035 Gap Domain Contract
- **Extended by:** ADR-037 Versioned Gap Completion Checklist and Critical Rule Pack

## Context

AI-03 requires Gap detection from structured Context, active Requirements and a Project-type
Completion Checklist, followed by deterministic Critical rules. The approved Completion Checklist
and Critical Rule Pack do not yet exist. The owner therefore split J02 so the provider-neutral,
transaction-safe foundation can proceed without turning model-proposed Critical severity into an
authoritative Scope-readiness decision.

## Decision

- Input is an exact snapshot of `context_version`, Project type, explicit
  `completion_checklist_version`, Context Item `(id, updated_at)` revisions for
  `proposed|confirmed`, and Requirement `(id, updated_at)` revisions for `draft|confirmed`.
  Membership or revision drift at final persistence raises `GAP_SNAPSHOT_CHANGED`; the same Job
  never refreshes to a newer snapshot.
- Candidate output is exactly `gap_type`, `severity`, `explanation`, `source_refs`,
  `affected_requirement_ids` and versioned `suggested_resolution_type`. `question` remains J03.
- Resolution values are `provide_information`, `clarify_ambiguity`, `resolve_conflict`,
  `make_decision`, `validate_assumption`, and `mitigate_scope_risk`.
- `affected_requirement_ids` is normalized relationally in `gap_requirement_links`; it is not
  stored in JSONB. Database constraints anchor both sides to the same Account and Project, and a
  database trigger rejects a different Context snapshot.
- An exact duplicate has the same type, severity, explanation, resolution, canonically ordered
  Source References and canonically ordered Requirement IDs. Any duplicate rejects the complete
  Batch as `DUPLICATE_GAP`; no semantic merge, fuzzy match, embedding or LLM judge is used.
- Empty AI output is a successful zero-Gap result. Gap rows, link rows and Job terminal
  `gap_count` metadata commit atomically. Usage Ledger appends remain independent and occur once
  per AI/repair call.
- Replay resolves a same-tenant terminal Job before AI execution. A successful replay verifies
  stored `gap_count` against rows linked by `generation_job_id`, including zero; failed replay
  returns the stored safe error. Replay creates no AI, Usage or persistence side effect.
- `CriticalGapRuleEvaluator` is a provider-neutral port. J02-A contains no rule implementation.
  Model-proposed `severity=critical` may be stored as a candidate attribute, but is not an
  authoritative Scope/Release blocker unless a future approved deterministic evaluator matches it.
- The existing private `jobs.payload_ref` stores the `gap_count` result key without replacing
  existing metadata. No second generation-result table is created.

## Atomicity and repair

Schema, vocabulary, provenance, affected-Requirement and exact-duplicate defects are eligible for
the explicit bounded repair policy. Snapshot, persistence, Provider and tenant failures are not.
The final transaction commits every validated Gap, link and Job-result mutation or none.

## Safe observability

Required events are `gap.detection_started`, `gap.detection_completed`, `gap.detection_failed`,
`gap.snapshot_changed`, `gap.duplicate_rejected`, and `gap.replay_served`. Only approved IDs,
versions, counts, duration, status and reason codes are emitted. Explanation, Context/Requirement
text, Source References, affected IDs, prompt and raw model output are prohibited.

## Deferred / blocked at the J02-A decision point

- S1-J02-B was deferred here; ADR-037 now supplies its approved Checklist, rule definitions,
  precedence/versioning and fixtures.
- J03: question, Clarification and accepted-assumption actor/timestamp semantics.
- Public Gap API/UI, concrete Provider, Queue scheduling/ACK/retry and Scope-readiness integration.

This ADR records the J02-A boundary. ADR-037 later approved and specifies J02-B; full S1-J02 is
complete only when the combined implementation and verification pass.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J02; read 2026-09-09
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03; read 2026-09-09
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06; read 2026-09-09
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap/Job baseline; read 2026-09-09
- Owner-approved J02-A split and refinements dated 2026-09-09.
