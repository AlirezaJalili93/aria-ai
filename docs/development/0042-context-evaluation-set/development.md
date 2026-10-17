# Development Record: 0042 — Context Evaluation Set

- **Status:** COMPLETE
- **Increment:** S1-H05
- **Source sync date:** 2026-09-06
- [Test report](./test-report.md)

## Scope

Implemented the accepted versioned Context Structuring evaluation set with 20 synthetic Persian
fixtures, deterministic Fake Provider, executable metric/threshold calculations, machine-readable
Human Review Rubric, redacted report generation and Contract/Regression tests. This increment does
not select or invoke a real Provider and does not change production runtime behavior.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H05
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — §§9, 23–33
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — AI Eval Gate
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Sprint 1 AI Evaluation
- [ADR-029 — Context Structuring Evaluation Set Contract](../../adr/ADR-029-context-evaluation-set-contract.md)
- Owner approval for H05 implementation dated 2026-09-06

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4201 | Backlog S1-H05; ADR-029 §§1–2 | `evals/context-structuring/context_structuring_eval_v1/manifest.json`, schemas and `fa_ctx_001..020` | TC-4201 |
| REQ-4202 | ADR-029 §3; owner-approved accuracy clarification | `scripts/context-evaluation.mjs` pooled metrics and exact aligned-decision formula | TC-4202, TC-4203 |
| REQ-4203 | ADR-029 §4 | `thresholds.json` and executable direction-aware threshold assessment | TC-4204 |
| REQ-4204 | ADR-029 §5 | `human-review-rubric.json` with two-reviewer/adjudication/pass rules | TC-4204 |
| REQ-4205 | ADR-029 §6; owner guardrails | Fake Provider boundary, redacted fixture-only report and explicit `model_quality_gate=not_run` | TC-4202, TC-4205 |
| REQ-4206 | Test Master AI Eval Gate | Contract, unsafe provenance, malformed response, failure and regression tests in repository CI | TC-4201–TC-4206 |

## Assumptions and Clarifications

- Classification accuracy uses the approved executable denominator: every gold item once plus every
  unmatched predicted item once; only correctly classified one-to-one matches enter the numerator.
- A declared expected failure such as `INSUFFICIENT_CONTEXT` is a valid first-pass contract outcome
  when it produces no items and uses an allowed stable failure code.
- Persian quality remains `not_run` until human review scores exist; no synthetic score is fabricated.
- Fake Provider results validate the harness only and never promote the Model Quality gate.
- **Unapproved assumptions:** None

## Changes

- Accepted ADR-029 and aligned its classification-accuracy prose with the executable evaluator.
- Added 20 stable synthetic Persian fixture IDs under `context_structuring_eval_v1`, covering clear,
  ambiguous, incomplete, contradictory, fragmented, mixed-language, multi-source, insufficient and
  prompt-injection scenarios across the three approved Project types.
- Added fixture/report JSON schemas, approved threshold metadata and the deterministic Human Review
  Rubric with reviewer, adjudication and pass-score rules.
- Added a dependency-free evaluator and deterministic Fake Provider that calculate pooled source
  trace, unsupported-assumption, classification, first-pass and repaired-JSON metrics.
- Added threshold assessment, explicit Contract/Model-Quality gate separation and a CLI that creates
  parent directories and writes only redacted report data.
- Added negative-path tests for invalid provenance, unsupported assumptions, malformed items and the
  exact classification denominator; integrated the suite into `npm test` and CI contract tests.

## Structure Preservation

- All fixture content, gold output and evaluation-only code stay under `evals/` or `scripts/`; no
  Domain, Application, API, Worker, database schema or public API contract changed.
- No Provider SDK, model name, credential name, prompt, timeout or retry policy was introduced.
- The Fake Provider is an evaluation boundary and does not enter production dependency composition.
- Reports contain fixture IDs, versions, metrics and failure categories only; Persian input, gold
  content, Provider output and raw payloads are excluded.

## Senior Review

- Confirmed fixture inventory matches the manifest exactly and all 25 JSON artifacts parse.
- Confirmed the approved accuracy definition is identical in ADR, evaluator and regression tests.
- Hardened malformed-output handling so invalid Provider items produce contract failures rather than
  crashing metric aggregation.
- Confirmed required provenance distinguishes an empty allowed `source_refs` array from a missing
  trace on a trace-required item, and half-open offsets are bounded to the matching source version.
- Confirmed threshold assessment is executable but Model Quality remains explicitly `not_run` for
  Fake Provider runs; Persian Quality is never inferred automatically.
- Confirmed the CLI report contains no fixture text, expected output or Provider payload.
- Resolved a repository-wide secret-scan false positive in the pre-existing Job Status API test by
  assembling its inert bearer fixture at runtime; no authentication behavior changed.

## Verification

- H05 focused suite: 8 passed.
- CI contract suite: 112 passed; the separate H05 suite passed 8 tests in the same `npm test` gate.
- Web suite: 19 passed.
- API suite: 197 passed, 68 PostgreSQL-dependent tests skipped because this evaluation-only increment
  was verified without setting `TEST_DATABASE_URL`; two environment/deprecation warnings only.
- Worker suite: 55 passed; one environment cache warning only.
- Lint, strict typecheck, production build, `npm test` and `npm run validate` passed.
- Repository secret scan passed after the inert Job Status token fixture was made scanner-safe.
- The final command evidence is recorded in the linked test report.

## Remaining Risks

- Real-model Persian quality, semantic correctness, attribution and hallucination performance remain
  unmeasured until G02/G03 selects a Provider and two human reviewers score a real run.
- The accepted 20-fixture v1 set has no gold item of canonical type `reference`; its perfect Fake
  output therefore yields six-class macro-F1 of `5/6`. Reference coverage should be considered when
  expanding toward the documented 30-fixture Sprint target, without rewriting v1 fixtures.
- Twenty synthetic fixtures are an internal Sprint baseline, not a final product benchmark or
  substitute for validated customer data.
