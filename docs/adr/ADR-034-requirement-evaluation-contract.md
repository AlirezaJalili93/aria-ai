# ADR-034: Requirement Extraction Evaluation Contract

- **Status:** Accepted — owner approval received 2026-09-07
- **Date:** 2026-09-07
- **Story:** S1-I05 — Requirement Eval
- **Extends:** ADR-029 Context Evaluation and ADR-031 Requirement Generation

## Context

The canonical Backlog and AI Workflow require Requirement recall, unsupported-output, duplicate
and Persian clarity/actionability evaluation. They do not define deterministic alignment,
critical-omission semantics, denominators or thresholds. The owner froze those details for a
Sprint-1 internal-alpha evaluation set. This contract remains provider-neutral and does not select
or execute G02/G03.

## Dataset and deterministic alignment

- The immutable dataset ID is `requirement_extraction_eval_v1` and contains exactly 20 synthetic
  Persian fixtures `fa_req_001` through `fa_req_020`. Changing Gold content creates a new dataset
  version; v1 is never silently rewritten after release.
- The set covers clear, ambiguous, incomplete, contradictory, unsupported and duplicate-potential
  inputs, all six Requirement categories and all three Project types.
- Inputs are versioned Structured Context, not customer data. Gold Requirements contain stable
  `gold_requirement_id`, provenance, support expectation and an Eval-only
  `critical_for_scope` annotation.
- `critical_for_scope` never enters the Requirement Domain, database or public API. It means that
  omitting the Requirement would misrepresent the primary client need, lose a key implementation
  decision, or prevent a reliable Scope.
- Fake/CI alignment is fixture-annotated and deterministic. It uses no LLM judge, embeddings,
  fuzzy matching or hidden similarity threshold. Real-provider semantic alignment requires human
  review and remains deferred.
- Semantic duplicate groups are fixture annotations. For CI, group membership is explicit and
  deterministic; no fuzzy duplicate decision is performed by the evaluator.

## Metrics

All aggregate ratios use pooled raw counts and exact division. Fixtures with no denominator never
receive an artificial perfect score.

```text
requirement_recall = unique matched Gold Requirements / all Gold Requirements

critical_omission_rate = unmatched critical Gold Requirements / all critical Gold Requirements

unsupported_output_rate = semantically unsupported generated Requirements / all generated Requirements

unsupported_detection_rate = correctly flagged unsupported Requirements / all unsupported generated Requirements

duplicate_rate = sum(max(0, present candidates in semantic duplicate group - 1)) / all generated Requirements
```

- Any unmatched `critical_for_scope` Gold Requirement is a Release Blocker independently of the
  aggregate critical-omission value.
- Any critical unsupported generated Requirement not detected with `is_unsupported=true` is a
  Release Blocker.
- A correctly flagged unsupported output still contributes to `unsupported_output_rate`, while it
  contributes positively to `unsupported_detection_rate`; generation quality and safety detection
  are not conflated.
- `unsupported_detection_rate` is `N/A` when no unsupported output exists. This is non-blocking for
  a Real Provider quality run, but deterministic CI must separately prove detector behavior with
  annotated unsupported candidates.
- If no Requirements are generated, unsupported, duplicate, clarity and actionability metrics are
  `N/A`. Recall and critical omission remain responsible for failing that run.
- The dataset is invalid unless its pooled Gold denominator and pooled critical-Gold denominator
  are both non-zero.

## Human review

- Two independent fluent-Persian reviewers score every generated Requirement separately for
  `clarity_score` and `actionability_score` on a 1..5 scale.
- A score of 1 is unusable, 3 is understandable/usable only after material editing, and 5 is
  precise and directly usable without material editing.
- If reviewer scores differ by at least two points for a dimension, adjudication is mandatory for
  that dimension. The adjudicated value replaces the disputed dimension; otherwise the final
  value is the arithmetic mean of the two scores.
- Dataset clarity/actionability are pooled means across all rated generated Requirements. With
  `N_generated=0`, both are `N/A`; `N/A` cannot make the Quality Gate pass.

## Frozen threshold matrix

| Metric | Release Blocker | Minimum Acceptable | Target |
| --- | ---: | ---: | ---: |
| `requirement_recall` | `< 0.80` | `>= 0.90` | `>= 0.95` |
| `critical_omission_rate` | `> 0`, or any critical Gold unmatched | `0` | `0` |
| `unsupported_output_rate` | `> 0.15` | `<= 0.10` | `<= 0.05` |
| `unsupported_detection_rate` | `< 0.90`, or any critical miss | `>= 0.95` | `1.00` |
| `duplicate_rate` | `> 0.10` | `<= 0.05` | `0` |
| `clarity_score` | `< 3.5`, or a critical Requirement `< 3` | `>= 4.0` | `>= 4.5` |
| `actionability_score` | `< 3.5`, or a critical Requirement `< 3` | `>= 4.0` | `>= 4.5` |

Gate interpretation is exact: any blocker stops release; absence of a blocker but any metric below
Minimum is still a failed Quality Eval requiring iteration; all Minimums allow Internal Alpha; all
Targets mark Target Quality Achieved.

## Provider and privacy boundary

- Contract/CI uses a deterministic Fake Provider to prove fixtures, annotations, denominators,
  `N/A`, blocker detection and safe report generation. A Fake Provider pass is never model-quality
  evidence.
- Real Provider execution and human semantic alignment wait for G02/G03. No Provider/model/SDK,
  endpoint, credential, retry or timeout is selected here.
- Reports/logs may contain fixture ID, versions, metric values/counts, pass/fail, failure category
  and duration. Fixture Context, Gold or generated title/description, Source References, raw
  Provider response, prompt and reviewer free-text notes are prohibited.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I05 and Sprint Eval baseline
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-02 Requirement Extraction
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — AI Evaluation
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Requirement Eval and Provider gates
- Owner-approved baseline, refinements and frozen thresholds dated 2026-09-07.
