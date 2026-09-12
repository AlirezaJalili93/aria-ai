# Development Record: 0053 — Gap Detection Evaluation

- **Status:** COMPLETE
- **Increment:** S1-J05
- **Source sync date:** 2026-09-12
- **Completed:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Implement the approved Eval-only `gap_detection_eval_v1` contract: 20 immutable Persian synthetic
fixtures, executable provenance and affected-Requirement annotations, deterministic Fake Provider,
Gap Recall/critical Recall/false-gap/critical precision/semantic-validity metrics, frozen thresholds,
Critical Rule Pack alignment, two-reviewer semantic rubric, privacy-safe reports and regression tests.
Real Provider quality execution remains deferred until G02/G03.

No Runtime, Domain, API, Migration, Worker, Queue, J02, J03 or J04 behavior is changed.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J05; synchronized 2026-09-12
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03; synchronized 2026-09-12
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — AI Evaluation; synchronized 2026-09-12
- [ADR-037](../../adr/ADR-037-gap-critical-rule-pack.md)
- [ADR-040](../../adr/ADR-040-gap-evaluation-contract.md)
- Owner-approved J05 refinements dated 2026-09-12.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-5301 | J05 frozen dataset contract | `evals/gap-detection/gap_detection_eval_v1` | TC-5301, TC-5302 |
| REQ-5302 | Executable provenance/affected-Requirement annotations | `scripts/gap-evaluation.mjs` | TC-5303 |
| REQ-5303 | Gap Recall and Critical Recall formulas | `scripts/gap-evaluation.mjs` | TC-5304 |
| REQ-5304 | False Gap Rate and Critical Precision formulas | `scripts/gap-evaluation.mjs` | TC-5305 |
| REQ-5305 | Critical Rule Pack v1 alignment and blockers | `scripts/gap-evaluation.mjs` | TC-5306, TC-5307 |
| REQ-5306 | Semantic validity review and adjudication | `scripts/gap-evaluation.mjs` | TC-5308 |
| REQ-5307 | Frozen thresholds and gate semantics | `thresholds.json`, evaluator | TC-5309 |
| REQ-5308 | Fake/Real Provider boundary | `scripts/gap-evaluation.mjs`, ADR-040 | TC-5310 |
| REQ-5309 | Privacy-safe report/logging | evaluator report projection | TC-5311 |
| REQ-5310 | Documentation and repository quality gates | this record and report | TC-5312 |

## Assumptions and Clarifications

- J05 evaluates Gap Detection outputs only; it does not modify or reinterpret the J02 Rule Pack.
- `critical_for_scope` is an Eval-only Gold annotation and is never persisted or exposed by Runtime.
- Fake Provider output is harness evidence only. Real-provider semantic quality is not validated.
- Fixture content is synthetic Persian and contains no customer data.

**Unapproved assumptions:** None

## Changes

- Added ADR-040 with the frozen J05 Dataset, matching, metric, threshold, human review, privacy and
  provider contracts.
- Added `gap_detection_eval_v1` manifest, schemas, thresholds, rubric and exactly 20 Persian
  synthetic fixtures covering all six Gap Types and three Project Types, including no-Gap cases.
  Fixture `source_versions` metadata makes canonical-text lengths executable for offset-bound
  provenance validation.
- Added deterministic Fake Provider/Evaluator with executable source-ref expectations, affected
  Requirement checks, Critical Rule Pack authority, pooled metrics, `N/A` handling and gate output.
- Added two-reviewer semantic-validity handling with difference-two adjudication and Critical score
  blockers.
- Added privacy-negative Regression tests and the J05 suite to `npm run test:eval`.
- Added evaluator documentation to `evals/README.md`.

## Structure Preservation

- Evaluation assets remain under `/evals`; the harness remains under `/scripts`.
- No Runtime Domain/Application module, API route, database table, migration, Worker task, Provider
  SDK, Queue dependency or UI surface was added.
- J02 Critical Rule Pack remains the only runtime Critical authority.
- Report projection contains identifiers, versions, counts, metric values, statuses and failure
  categories only; source/content/provenance payloads are excluded.

## Senior Review

**Status:** PASS.

- Confirmed Critical Recall is separate from Critical Precision and has a strict 100% threshold.
- Confirmed the Critical Precision denominator contains only Rule-Pack-classified generated
  Critical Gaps; raw model severity without Rule authority is a contract failure.
- Confirmed `source_refs_expectation` is executable and invalid references fail even when optional.
- Confirmed provenance offsets are bounded by the fixture's declared canonical-text length.
- Confirmed one-to-one Candidate/Gold matching; many-to-many matching is rejected.
- Confirmed duplicate, provenance and affected-Requirement failures cannot be hidden by metrics.
- Confirmed Human Review uses final adjudicated semantic scores and blocks Critical scores below 3.
- Confirmed Fake Provider can report only harness status and Real Provider remains deferred to G02/G03.
- Confirmed no Runtime or prior J02/J03/J04 contract was changed.

## Verification

See [test-report.md](./test-report.md). The final run includes J05 Eval tests, all prior Eval suites,
Contract CI, Web/API/Worker tests, lint, typecheck, production build, architecture validation,
secret scan and diff hygiene.

## Remaining Risks

- Real AI Gap quality, semantic matching and human evidence remain unvalidated until a Provider is
  formally selected under G02/G03.
- The 20-fixture set is Sprint 1 baseline, not a final production benchmark.
- No database or Runtime behavior was changed; J05 cannot improve J02 quality by itself.
