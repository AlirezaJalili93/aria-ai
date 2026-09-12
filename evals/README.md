# AI Evaluations

Deterministic fake workflows and real-provider evaluation sets are added with AI stories. Sprint 1 requires at least 20 Persian fixtures before AI workflow acceptance.

## Context structuring v1

`context-structuring/context_structuring_eval_v1` contains the accepted S1-H05 synthetic Persian
fixture set, schemas, thresholds and human-review rubric. Run the deterministic contract harness with:

```text
npm run test:eval
node scripts/context-evaluation.mjs --output .tmp/h05-fake-report.json
```

The generated report contains fixture identifiers, metrics and failure categories only. It excludes
fixture input and expected/provider output. A passing Fake Provider run validates orchestration,
schemas, provenance checks and metric calculations; it is not evidence of model quality. Real-model
evaluation remains blocked until the separate G02/G03 Provider Selection decision.

## Requirement extraction v1

`requirement-extraction/requirement_extraction_eval_v1` contains the frozen S1-I05 synthetic
Persian fixtures, deterministic annotations, threshold matrix and two-dimension review rubric.

```text
npm run test:eval
node scripts/requirement-evaluation.mjs --output .tmp/i05-fake-report.json
```

The Fake Provider report proves only annotation matching, formulas, denominator/`N/A` handling,
critical blocker detection and report privacy. Real-provider quality execution remains deferred to
G02/G03.

## Gap detection v1

`gap-detection/gap_detection_eval_v1` contains the frozen S1-J05 set of 20 synthetic Persian
fixtures, executable provenance/affected-Requirement annotations, Critical Rule Pack alignment,
thresholds and semantic-validity review rubric.

```text
npm run test:eval
node scripts/gap-evaluation.mjs --output .tmp/j05-fake-report.json
```

The Fake Provider can only produce `EVAL HARNESS PASS`; it never declares AI quality acceptance.
Critical recall, rule-backed precision, false-gap rate, semantic validity and all item-level
blockers are evaluated without logging fixture or customer content. Real-provider quality remains
deferred until G02/G03.

Platform candidate experiments live under `durable-queue/`. Celery, Dramatiq and RQ are locked and
tested in separate Compose projects. They remain isolated from runtime dependencies until measured
evidence and an accepted ADR authorize adoption.

