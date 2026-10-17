# Development Record: 0050 — Gap Critical Rules

- **Status:** COMPLETE (S1-J02-A + S1-J02-B verified; full S1-J02 complete)
- **Increment:** S1-J02-B
- **Source sync date:** 2026-09-09
- [Test report](./test-report.md)

## Scope

Implement the approved `completion_checklist_v1`, provider-neutral untrusted AI Rule Signal
sidecar, `critical_gap_rule_pack_v1`, deterministic validation/severity assignment, immutable
rule-generated Persian Gap templates, fail-closed policy lookup, policy-version Job pinning and
safe observability. Verify J02-A and J02-B together before declaring full S1-J02 complete.

J03 questions/Clarifications, persisted semantic attributes, concrete Provider/Worker wiring,
Scope Readiness integration and real-provider quality evaluation remain explicit non-goals.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J02
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap baseline
- [ADR-036 — Gap Detection Foundation](../../adr/ADR-036-gap-detection-foundation.md)
- [ADR-037 — Gap Critical Rule Pack](../../adr/ADR-037-gap-critical-rule-pack.md)
- Owner-approved J02-B frozen contract dated 2026-09-09.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-5001 | Owner-approved Completion Checklist Matrix | `gap_detection.py::COMPLETION_CHECKLIST_V1` | TC-5001 |
| REQ-5002 | Sidecar is untrusted structured AI evidence | Rule Signal dataclasses and validation | TC-5002 |
| REQ-5003 | CGR-001 missing Critical checklist coverage | `VersionedCriticalGapRuleEvaluator` | TC-5003 |
| REQ-5004 | CGR-002 conflict over at least one Key Requirement | `VersionedCriticalGapRuleEvaluator` | TC-5004 |
| REQ-5005 | CGR-003 unconfirmed sensitive assumption | `VersionedCriticalGapRuleEvaluator` | TC-5005 |
| REQ-5006 | Rule-generated immutable-template Gap | Critical evaluator and evaluated Batch | TC-5006 |
| REQ-5007 | AI Critical without Rule Match becomes High | `_apply_critical_evaluation` | TC-5007 |
| REQ-5008 | Stable Rule precedence and complete match retention | Critical evaluator | TC-5008 |
| REQ-5009 | Fail-closed policy and Job version pinning/replay | Use case and SQLAlchemy repository | TC-5009 |
| REQ-5010 | Ordered validation, atomic persistence and safe logging | Use case, repository, contract tests | TC-5010 |
| REQ-5011 | AGENTS documentation and quality gates | This record and linked report | TC-5011 |

## Assumptions and Clarifications

- Semantic signal extraction may be AI-assisted; validation and final Critical severity assignment
  are deterministic and versioned.
- The Checklist Matrix, `project.objective` Critical classification, and Corporate/Portfolio
  Critical items are new owner-approved J02-B decisions, not claims about earlier source wording.
- `risk_domain` is a closed AI Signal classification and is never persisted on Context Item.
- Key Requirement is exactly `status IN (draft, confirmed) AND priority=must`.

**Unapproved assumptions:** None

## Changes

- Added immutable Checklist and Rule Pack contracts plus three typed Rule Signal variants.
- Added full Checklist-signal coverage checks, exact Snapshot-reference validation, candidate-link
  consistency and fail-closed policy resolution.
- Added CGR-001/002/003, fixed processing order, synthetic Gap templates and downgrade of
  unverified model Critical severity.
- Added Job metadata pinning for both versions and Critical/rule-generated result counters while
  preserving existing private metadata and replay compatibility.
- Added Python unit/integration tests, Node contract checks and ADR-037.

## Architecture and Design Decisions

ADR-037 is authoritative for J02-B. Domain/Application remains provider-neutral. No Provider SDK,
Queue framework, public API, schema table, deployable service or persisted semantic attribute was
added.

## Structure Preservation

- Extended the existing `CriticalGapRuleEvaluator` Application port and J02-A orchestration.
- Kept SQLAlchemy and Job JSONB persistence in the Infrastructure adapter.
- Preserved Gap/Requirement relational links and the existing Alembic head; no DB schema migration
  was needed.
- Preserved exact-Snapshot and transaction boundaries established by ADR-036.

## Senior Review

**Status:** PASS.

Interim review added stable Rule processing order and candidate-link consistency validation so an
AI Sidecar cannot elevate an unrelated Candidate. Final review additionally found that private
replay counters were accepted without comparison to persisted Gap rows; replay now rejects a
corrupt Critical count or impossible rule-generated count. Confirmed that Rule Signals remain
transient/untrusted, rule templates are immutable, Critical downgrade is enforced before writes,
policy failure is non-retryable, metadata preserves existing keys, and no sensitive content enters
structured events. No unresolved High/Medium finding remains.

## Verification

Focused combined Application/Rule/PostgreSQL tests: 32/32 PASS. Contract CI: 134/134 PASS; Eval:
24/24 PASS; Web: 26/26 PASS; API: 407/407 PASS with PostgreSQL; Worker: 57/57 PASS. Full lint,
TypeScript/Python typecheck and production build PASS. Final documentation validation, secret scan
and complete `npm test` result are recorded in the linked report. Architecture validation passed
22/22 checks and the secret scan inspected 602 publishable text files.

## Remaining Risks

- Real semantic signal recall remains AI-assisted and requires J05 real-provider evaluation.
- Concrete Provider/Worker scheduling and Scope Readiness integration remain deferred by contract.
