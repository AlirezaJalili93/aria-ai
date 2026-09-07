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

Platform candidate experiments live under `durable-queue/`. Celery, Dramatiq and RQ are locked and
tested in separate Compose projects. They remain isolated from runtime dependencies until measured
evidence and an accepted ADR authorize adoption.

