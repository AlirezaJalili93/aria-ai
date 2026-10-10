# ADR-037: Versioned Gap Completion Checklist and Critical Rule Pack

- **Status:** Accepted for S1-J02-B — owner approval received 2026-09-09
- **Date:** 2026-09-09
- **Story:** S1-J02-B — Completion Checklist and Critical Gap Rules
- **Extends:** ADR-036 Gap Detection Foundation

## Context

AI-03 requires deterministic Critical rules after AI Gap output. The approved source documents
describe three Critical examples but do not define the Project-type Completion Checklist, the
machine-readable signal contract, or exact rule predicates. The owner approved the new Sprint 1
matrix and rule pack as canonical J02-B decisions on 2026-09-09.

The semantic extraction step remains AI-assisted: a model can fail to recognize missing checklist
coverage, a Requirement conflict, or a sensitive assumption. Therefore `rule_signals` are
untrusted structured AI evidence, not deterministic truth. Schema/snapshot validation and final
Critical severity assignment are deterministic and versioned.

## Decision

### Versioning

- Checklist version: `completion_checklist_v1`.
- Rule-pack version: `critical_gap_rule_pack_v1`.
- Every completed Job pins both versions in private Job metadata. Replay uses that completed
  result and its pinned versions; it never evaluates against a newer policy.
- Missing/unknown Project type, Checklist version, or Rule Pack fails closed as
  `GAP_CRITICAL_POLICY_UNAVAILABLE`, `retryable=false`, before Gap/link/outbox persistence.

### Completion Checklist v1

All items are required. `Critical` below means a missing item matches CGR-001.

| Project type | Checklist item | Critical when missing |
| --- | --- | --- |
| All | `project.objective` | Yes |
| Landing | `project.target_audience` | Yes |
| Landing | `landing.primary_cta` | Yes |
| Landing | `landing.offer_or_value_proposition` | No |
| Landing | `landing.required_content_or_sections` | No |
| Corporate | `project.target_audience` | No |
| Corporate | `corporate.services_or_offerings` | Yes |
| Corporate | `corporate.required_pages` | Yes |
| Corporate | `corporate.contact_path` | No |
| Portfolio | `project.target_audience` | No |
| Portfolio | `portfolio.professional_identity` | Yes |
| Portfolio | `portfolio.work_or_case_study_inventory` | Yes |
| Portfolio | `portfolio.contact_path` | No |

The Critical classification of `project.objective` and the listed Corporate/Portfolio items is a
new owner-approved J02-B decision; it is not represented as a pre-existing AI Workflow mandate.

### Untrusted AI rule signals

The provider-neutral sidecar supports `checklist_item`, `requirement_conflict`, and
`critical_assumption` signals. Provider output may only use `signal_origin=ai_candidate`.

- Every applicable Checklist item must have exactly one `present|missing` signal.
- `present` requires one or more supporting Context Item IDs from the exact Snapshot.
- `missing` requires no supporting IDs and means only that AI introduced no support.
- A Requirement conflict requires at least two distinct Requirement IDs from the exact Snapshot.
- A Critical-assumption signal references an exact-Snapshot `assumption` that is not confirmed.
  Its closed AI classification is `payment|security|external_integration`; it is not persisted on
  Context Item.
- A linked Candidate index must exist and match the expected Gap type. Conflict Candidate links
  must contain exactly the signalled Requirement set.

### Deterministic rule pack v1

- `CGR-001`: required Checklist item is `missing` and `critical_if_missing=true` -> Critical.
- `CGR-002`: Requirement-conflict signal references at least one Requirement with
  `status IN (draft, confirmed) AND priority=must` -> Critical. Removed/superseded Requirements are
  outside the Snapshot and never Key Requirements.
- `CGR-003`: Critical-assumption signal references an unconfirmed `assumption` and its AI risk
  classification is in the closed sensitive-domain enum -> Critical.

Processing/reporting order is `CGR-003`, `CGR-002`, `CGR-001`. All matches are retained as a
stable transient set; precedence never removes other evidence. If a valid matching Signal has no
Candidate link, the Rule Pack produces a Critical Gap using its immutable Persian explanation
template. Model-proposed Critical without a matching Rule is normalized to High and cannot block
Scope Readiness.

## Validation and atomicity

The order is: Candidate schema -> Rule Signal schema -> Snapshot references -> Checklist/policy ->
Critical evaluation -> synthetic Gap creation -> exact duplicate validation -> exact Snapshot
recheck -> atomic persistence. A failure before commit writes no Gap, Requirement link, or business
Outbox record. Usage metering remains independent under ADR-036.

## Safe observability

Allowed fields include Job/Account/Project IDs, Context and policy versions, Rule ID or matched
count, AI Candidate count, rule-generated count, Critical count, duration and reason code. Context
or Requirement text, Gap explanation, Source References, raw Rule Signals, raw provider response
and prompt are prohibited.

## Deferred

- End-to-end deterministic semantic attributes on Context Items.
- J03 questions, Clarifications and accepted-assumption workflow.
- J05 real-provider Gap quality evaluation and thresholds.
- Concrete Provider/Worker/Queue wiring and Scope-readiness integration.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J02; read 2026-09-09
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03; read 2026-09-09
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06; read 2026-09-09
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap baseline; read 2026-09-09
- Owner-approved J02-B contract and refinements dated 2026-09-09.
