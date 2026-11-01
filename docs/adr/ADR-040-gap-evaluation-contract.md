# ADR-040: Gap Detection Evaluation Contract

- **Status:** Accepted — owner approval received 2026-09-12
- **Date:** 2026-09-12
- **Story:** S1-J05 — Gap Eval
- **Extends:** ADR-037 Gap Critical Rule Pack

## Decision

J05 is an Eval-only increment. It adds the immutable `gap_detection_eval_v1` dataset, a
deterministic Contract/CI harness, report schemas, thresholds and regression tests. It does not
change Gap runtime behavior, J02 rules, J03 Clarifications, J04 UI, API, database or worker code.

## Dataset

- Exactly 20 synthetic Persian fixtures: `fa_gap_001` through `fa_gap_020`.
- Project types are `landing`, `corporate` and `portfolio`; all six canonical Gap Types occur:
  `missing_information`, `ambiguity`, `conflict`, `unsupported_assumption`, `decision_required`
  and `scope_risk`.
- Dataset validity requires `total_gold_gaps > 0`, `total_gold_critical_gaps > 0`, at least one
  no-Gap fixture, every Gap Type and every Project Type at least once.
- `critical_for_scope` is Eval-only and never enters the Gap Domain, database, API or runtime logs.
- Gold changes require a new eval-set version; v1 is immutable.

## Matching and executable annotations

- Contract/CI matching is deterministic and annotation-driven. No LLM judge, embedding, fuzzy
  matching or hidden similarity threshold is allowed.
- A Candidate may match at most one Gold Gap and a Gold Gap may have at most one canonical
  Candidate. Many-to-many matching is forbidden in v1.
- A complete match requires semantic issue match and `gap_type` match. Severity mismatch does not
  reduce `gap_recall`; critical/rule correctness is evaluated separately.
- `source_refs_expectation` is executable: `empty` requires `[]`, `required` requires at least one
  valid reference, and `optional` allows zero or valid references. Invalid references always fail.
- Duplicate Gap candidates fail the Contract Gate according to J02 duplicate policy.

## Metrics

All aggregate ratios use pooled raw counts and exact division.

```text
gap_recall = matched_gold_gaps / total_gold_gaps
critical_gap_recall = matched_gold_critical_gaps / total_gold_critical_gaps
false_gap_rate = unmatched_generated_gaps / total_generated_gaps
critical_gap_precision = correctly_rule_supported_critical_generated_gaps /
                         all_rule_classified_critical_generated_gaps
semantic_validity_score = pooled final adjudicated reviewer score / rated generated gaps
```

Raw model severity is not authoritative. A generated Critical Gap must be classified by
`critical_gap_rule_pack_v1` and carry the expected applicable Rule ID. Critical without valid Rule
authority is `critical_rule_mismatch`, a Contract Failure and Release Blocker.

Zero-denominator metrics are `N/A`, never zero or 100%: `gap_recall`, `critical_gap_recall`,
`false_gap_rate`, `critical_gap_precision` and `semantic_validity_score` each preserve this rule.
The aggregate Dataset must satisfy all required denominator invariants or return
`INVALID_EVAL_DATASET`.

## Thresholds and gates

| Metric | Release Blocker | Minimum Acceptable | Target |
|---|---:|---:|---:|
| `gap_recall` | `< 0.80` | `>= 0.90` | `>= 0.95` |
| `critical_gap_recall` | `< 1.00` | `1.00` | `1.00` |
| `false_gap_rate` | `> 0.20` | `<= 0.10` | `<= 0.05` |
| `critical_gap_precision` | `< 0.90` | `>= 0.95` | `1.00` |
| `semantic_validity_score` | `< 3.5/5` | `>= 4.0/5` | `>= 4.5/5` |

Independent blockers:

- Any unmatched Critical Gold Gap.
- Any generated Critical without valid Rule Pack authority.
- Any Critical Gap with final semantic validity below 3.
- Any duplicate Gap, invalid provenance or invalid affected-Requirement relationship.

Gate interpretation is exact:

```text
Contract Failure -> EVAL INVALID/FAIL
Release Blocker -> RELEASE BLOCKED
No blocker but metric below Minimum -> QUALITY FAIL / ITERATION REQUIRED
All Minimums -> INTERNAL ALPHA QUALITY ACCEPTABLE
All Targets -> TARGET QUALITY ACHIEVED
```

The Fake Provider can only return `EVAL HARNESS PASS`; it cannot declare either quality status.

## Human review

Two independent fluent-Persian reviewers score `semantic_validity_score` from 1 to 5. A difference
of at least two points requires adjudication; final aggregate uses final adjudicated scores, not a
raw reviewer average. A no-output run is `N/A` and cannot pass the Quality Gate.

Human review can resolve semantic matching, but cannot override deterministic Critical Rule Pack
classification.

## Provider and privacy boundary

- CI uses a deterministic Fake Provider only.
- Real Provider quality evaluation is deferred until the G02/G03 Provider Selection decision.
- No Provider SDK, model name, credential, timeout, retry, fallback or endpoint is added by J05.
- Reports/logs may contain only eval IDs, versions, counts, metric values, threshold statuses,
  failure categories and duration. Context, Requirement, Gap, provenance, prompt, raw response and
  reviewer free text are prohibited.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J05; synchronized 2026-09-12
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03; synchronized 2026-09-12
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — AI Evaluation; synchronized 2026-09-12
- [ADR-037 — Gap Critical Rule Pack](./ADR-037-gap-critical-rule-pack.md)
- Owner-approved J05 refinements dated 2026-09-12.
