# Development Record: 0033 Parser Metrics

[Test report](./test-report.md)

## Scope

- Increment ID: `0033-parser-metrics`
- Story: `S1-F04 — Parser Metrics`
- Status: Completed
- Scope: provider-neutral parser metrics port, bounded dimensions, Text Parser latency/failure
  instrumentation and safe parser lifecycle logs.
- Explicitly deferred: metrics backend/vendor, dashboard/alerts, File Parser, Parser Job
  registration, Queue transport and retry policy.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-F04 metric names and Parser ordering; read 2026-09-05.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit?usp=drivesdk) — parser observability goals and failure categories; read 2026-09-05.
- [Aria AI Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — Worker/Application boundary and structured logging; read 2026-09-05.
- [ADR-019 — Text Parser Contract](../../adr/ADR-019-text-parser-contract.md)
- [ADR-020 — Parser Metrics Contract](../../adr/ADR-020-parser-metrics.md)
- Repository `AGENTS.md`

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3301 | S1-F04; ADR-020 | Provider-neutral `ParserMetrics` port for latency, queue wait and outcome recording | TC-3301 |
| REQ-3302 | Owner approval 2026-09-05; ADR-020 | `parse_latency` boundary includes parser work and excludes queue/persistence | TC-3302 |
| REQ-3303 | Owner approval; ADR-020 | Failure rate derives from terminal parser outcomes; bounded failure classes only | TC-3303, TC-3304 |
| REQ-3304 | Owner approval; ADR-020 | No tenant/project/source/job/free-text metric labels | TC-3301, TC-3304 |
| REQ-3305 | ADR-020; structured logging baseline | Safe parser lifecycle events use existing logger and trace context | TC-3305 |

## Changes

- Added Worker Application `ParserMetrics` protocol and bounded parser outcome validation.
- Instrumented `CanonicalTextParser` with injectable clock, parse latency and terminal outcome
  recording for success and empty/parse failures.
- Added safe `parser.parse_started`, `parser.parse_succeeded` and `parser.parse_failed` events
  without raw or canonical content.
- Added ADR-020, unit tests and repository contract tests.
- Kept queue timing as a provider-neutral port operation; no unapproved Queue/Job registration or
  metrics backend was introduced.

## Structure Preservation

- Metrics code remains in Worker Application and imports no Prometheus, OpenTelemetry, Redis,
  Celery, SQLAlchemy or provider SDK.
- Parser normalization, persistence schema, Queue runtime and Job lifecycle remain unchanged.
- No new deployable, migration, external integration or metrics backend was added.
- File Parser remains blocked by the separate DOCX/PDF reliability decision.

## Senior Review

- PASS: `parse_latency` starts and ends at the Text Parser boundary and excludes persistence and
  queue wait.
- PASS: `failure_rate` has an explicit terminal-outcome denominator and excludes canceled or
  never-started attempts.
- PASS: metric dimensions are bounded to parser type, outcome and the four approved failure
  classes; tenant/resource IDs and free text cannot become labels.
- PASS: parser logs use the existing structured logger and keep raw/canonical content out of logs.
- PASS: no metrics backend, Queue task registration, File Parser or retry policy was invented.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The owner approved the F04 contract definition on 2026-09-05. Backend selection, dashboard shape,
alerts and Parser Job timing integration remain explicitly deferred.

## Verification

See [test-report.md](./test-report.md). Focused tests and all repository gates passed.

## Remaining Risks

- A future Parser Job contract must provide the approved `available_at` and execution-start timing
  boundary before queue-wait observations can be emitted.
- A future metrics sink must derive failure rate from outcome counts while preserving bounded labels.
- File Parser remains blocked until DOCX/PDF reliability evidence and acceptance criteria are
  approved.

**Final status:** PASS
