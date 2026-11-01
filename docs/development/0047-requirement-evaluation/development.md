# Development Record: 0047 — Requirement Extraction Evaluation

- **Status:** COMPLETE
- **Increment:** S1-I05
- **Source sync date:** 2026-09-07
- [Test report](./test-report.md)

## Scope

Implement the frozen provider-neutral Requirement Extraction evaluation contract: 20 versioned
synthetic Persian fixtures, schemas, deterministic Fake Provider, annotation-driven evaluator,
frozen thresholds, two-dimension human-review rubric and privacy-safe report. Real Provider quality
execution remains deferred to G02/G03.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I05
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-02 Requirement Extraction
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — AI Evaluation
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Requirement Eval
- [ADR-031 — Requirement Generation](../../adr/ADR-031-requirement-generation-contract.md)
- [ADR-034 — Requirement Evaluation](../../adr/ADR-034-requirement-evaluation-contract.md)
- Owner-approved I05 contract and thresholds dated 2026-09-07.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4701 | I05 owner contract | Immutable v1 inventory of 20 Persian synthetic fixtures across approved segments/types | TC-4701 |
| REQ-4702 | I05 refinements | Stable Gold IDs and explicit deterministic match/duplicate/support annotations | TC-4702 |
| REQ-4703 | ADR-034 | Executable pooled Recall, critical omission, unsupported and duplicate formulas | TC-4703 |
| REQ-4704 | Frozen thresholds | Three-level assessments plus item-level critical blockers and exact `N/A` rules | TC-4704 |
| REQ-4705 | Human review contract | Independent clarity/actionability dimensions and difference-2 adjudication | TC-4705 |
| REQ-4706 | Provider strategy | Fake deterministic Contract Gate separated from deferred Real Provider Quality Gate | TC-4706 |
| REQ-4707 | Logging gate | Safe report and negative test excluding all prohibited content/free text | TC-4707 |
| REQ-4708 | AGENTS quality gate | ADR, records, full tests, review and validation | TC-4708 |

## Assumptions and Clarifications

- `critical_for_scope` and all candidate match/duplicate/support annotations are evaluation-only;
  none enters Requirement Domain, database, HTTP contracts or runtime logs.
- The Fake Provider proves evaluator mechanics only. No quality score from it is treated as model
  evidence and no real Provider is selected.
- **Unapproved assumptions:** None

## Changes

- Added accepted ADR-034 with the frozen dataset, metric formulas, threshold matrix, item-level
  blockers, denominator rules, human-review semantics and Provider boundary.
- Added immutable `requirement_extraction_eval_v1` metadata, JSON Schemas, threshold contract and
  two-reviewer clarity/actionability rubric.
- Added exactly 20 synthetic Persian fixtures with stable IDs, all approved Project types, all six
  Requirement categories, and clear/ambiguous/incomplete/contradictory/unsupported/
  duplicate-potential coverage.
- Added a deterministic Fake Provider and evaluator that use explicit fixture annotations for
  matching and duplicate groups, calculate pooled exact metrics, preserve `N/A`, and surface
  item-level critical blockers.
- Added a privacy-safe report format and negative tests that reject or exclude protected Eval
  content and reviewer free text.
- Added the Requirement evaluator to the repository `test:eval` gate without adding a runtime
  Provider, SDK, database field or product behavior.

## Structure Preservation

- Evaluation artifacts remain under `/evals`; executable harnesses remain under `/scripts`.
- Runtime Domain/Application and persistence contracts are unchanged.
- No Provider SDK, endpoint, credential or new deployable is introduced.

## Senior Review

- **Status:** PASS.
- Verified that matching and duplicate classification are annotation-driven and deterministic;
  there is no hidden LLM, embedding, fuzzy-match or text-similarity dependency in CI.
- Verified that unsupported generation quality and unsupported detection are independent metrics,
  while a critical detection miss remains an explicit item-level blocker.
- Verified zero denominators remain `N/A`, including `N_generated=0` for human scores, and never
  become artificial perfect scores.
- Closed a defense-in-depth mismatch found during review: runtime fixture validation now enforces
  unique deterministic Candidate IDs in addition to the JSON Schema constraint.
- Verified the evaluator output exposes only fixture IDs, counts, scores and controlled failure
  categories; Context, Requirement text, provenance, prompts, raw responses and reviewer notes are
  absent.
- Verified the Fake Provider can pass only the Contract Gate. The Model Quality Gate remains
  explicitly `not_run` until a real Provider and human evidence exist.

## Verification

- Focused Requirement evaluator: 16/16 PASS.
- Combined Context + Requirement Eval suite: 24/24 PASS.
- Full repository tests, lint, typecheck, production build, development-record validation, secret
  scan and diff hygiene: PASS. Exact commands and counts are recorded in the linked test report.

## Remaining Risks

- Real-provider quality and human-review evidence remain blocked on G02/G03.
