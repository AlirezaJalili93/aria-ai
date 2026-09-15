# Development Record: Durable Queue Candidate Evaluation

- Increment ID: `0026-durable-queue-evaluation`
- Date: 2026-09-05
- Owner: Platform Engineering
- Related plan/issue: S1-E02
- [Test report](./test-report.md)

## Scope

Build an isolated, local-only Celery candidate experiment for the documented durable Queue decision.
The increment measures worker-absent delivery, forced worker loss/redelivery, duplicate delivery and
idle Redis command usage. It does not adopt Celery in the Worker runtime, select product retry or
timeout values, deploy a new service, use the hosted Queue, or complete S1-E03/S1-E04.

## Source Documents

- User instruction on 2026-09-05 to continue after restoring Docker.
- Google Drive `Aria AI — Sprint 1 Technical Backlog v1.0`, S1-E02 and E2E-05; synced 2026-09-05.
- Google Drive `Aria AI — Final System Architecture v2.0`, sections 4, 5, 10, 20 and 24; synced 2026-09-05.
- Google Drive `13 — Aria AI — Accepted ADR Pack v1.0`, ADR-007 through ADR-010; synced 2026-09-05.
- Repository ADR-004, ADR-013 and `docs/architecture/durable-queue-evaluation-plan.md`.
- Celery 5.6.3 official documentation and PyPI release metadata, checked 2026-09-05.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-151 | S1-E02 | Isolated worker-absent and forced-loss probes | TC-2601, TC-2602 |
| REQ-152 | Accepted ADR-007/009 | Late-ack candidate configuration and duplicate-aware probe | TC-2602, TC-2603 |
| REQ-153 | Sprint 0 Queue Spike criteria | Redis visibility and idle-command instrumentation | TC-2604, TC-2605 |
| REQ-154 | ADR-004; user no-assumption rule | Candidate remains outside `apps/worker` and no framework is selected | TC-2606 |

## Assumptions and Clarifications

The owner approved an isolated Celery evaluation. All short durations and the dedicated local Redis
password are test-fixture parameters only; they are not product defaults or deployment decisions.

**Unapproved assumptions:** None

## Changes

- Added an exact, isolated Celery 5.6.3 lock under `evals/durable-queue/celery`; no runtime Worker
  dependency changed.
- Added a dedicated loopback Redis/Worker/probe Compose stack with a random per-run credential.
- Added a self-checking PowerShell runner for worker absence, forced loss/redelivery, duplicate
  outcome protection and idle command measurement.
- Added contract tests to the repository CI test set.
- Captured the owner-account Docker evidence: worker-absent delivery, forced-loss redelivery and
  duplicate delivery all retained exactly one committed probe outcome; the idle ten-second window
  consumed 36 local Redis commands.

## Architecture and Design Decisions

No ADR is accepted by this increment. An ADR may be proposed only after measured evidence is
available and the documented candidates can be compared.

## Structure Preservation

The candidate remains under `evals/`; Application, Domain, API, Worker runtime dependencies,
existing migrations and hosted infrastructure remain unchanged.

## Senior Review

The senior review removed a test-only legacy service kill, made each run reset only its dedicated
Compose volume, and added a worker-absent delay so stale state cannot create a false pass. Windows
PowerShell compatibility was corrected for random credential generation, and the probe received a
fixed CLI entrypoint after Docker proved that Compose arguments otherwise replaced the image CMD.
No runtime dependency, hosted binding, product retry value or Application/Domain behavior changed.

## Verification

The isolated Docker run emitted `QUEUE_EVALUATION_RESULT=PASS`. Contract, regression and
architecture commands are detailed in the [test report](./test-report.md). The final repository run
passed 6 record tests, 67 contract tests, 18 Web tests, 143 API tests and 16 Worker tests;
architecture validation passed all 22 checks.

## Remaining Risks

- Dramatiq and RQ have not been measured, so no framework selection is authorized.
- The 36-command local idle observation cannot establish hosted Upstash quota or cost behavior.
- Broker-unavailable Outbox recovery belongs to S1-E03; duplicate business-state protection belongs
  to S1-E04 and was represented here only by an isolated probe guard.
