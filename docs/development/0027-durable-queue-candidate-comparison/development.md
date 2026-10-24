# Development Record: Durable Queue Candidate Comparison

- Increment ID: `0027-durable-queue-candidate-comparison`
- Date: 2026-09-05
- Owner: Platform Engineering
- Related plan/issue: S1-E02
- [Test report](./test-report.md)

## Scope

Extend the isolated Queue spike to the two documented unmeasured candidates, Dramatiq and RQ. The
increment locks exact candidate versions and prepares equivalent black-box probes for worker
absence, forced Worker loss, duplicate delivery, delayed delivery and idle Redis usage. The owner
accepted the resulting Celery 5.6.3 framework/version decision after the comparison. This increment
does not modify the Aria Worker, adopt product retry/timeout values, deploy a service, use hosted
Queue data or implement S1-E03/S1-E04.

## Source Documents

- User instruction on 2026-09-05 to continue the documentation-driven development path.
- Product owner response `ادامه بده` on 2026-09-05 to the explicit ADR-015 approval request.
- Google Drive `Aria AI — Sprint 1 Technical Backlog v1.0`, S1-E02 and E2E-05; synced 2026-09-05.
- Google Drive `Aria AI — Final System Architecture v2.0`, durable Queue, retry and Release Gate sections; synced 2026-09-05.
- Google Drive `13 — Aria AI — Accepted ADR Pack v1.0`, ADR-007 through ADR-010; synced 2026-09-05.
- Google Drive Sprint 0 ADR Register, open Queue decision and spike criteria; synced 2026-09-05.
- Repository ADR-004, ADR-013 and `docs/architecture/durable-queue-evaluation-plan.md`.
- Dramatiq 2.2.1 PyPI metadata and official 2.2.x guide/reference; checked 2026-09-05.
- RQ 2.12.0 PyPI metadata and official Worker/Retry documentation; checked 2026-09-05.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-155 | Sprint 0 Queue decision | Exact isolated Dramatiq and RQ candidate locks | TC-2701 |
| REQ-156 | S1-E02; E2E-05 | Equivalent worker-absent and forced-loss probes | TC-2702, TC-2703 |
| REQ-157 | ADR-007/009 | JSON-only transport boundary and duplicate-aware outcome probe | TC-2704 |
| REQ-158 | Sprint 0 spike criteria | Native retry, delayed-delivery and idle-command measurements | TC-2705, TC-2706 |
| REQ-159 | ADR-004; user no-assumption rule | No runtime dependency or framework decision before comparison evidence | TC-2707 |

## Assumptions and Clarifications

The candidate heartbeat, maintenance, monitoring, delay and retry values are isolated experiment
fixtures used only to make bounded black-box observation possible. They are not Product or
Production defaults. Candidate behavior is tested without custom recovery logic or broker-state
time manipulation.

**Unapproved assumptions:** None

## Changes

- Added exactly locked Dramatiq 2.2.1 and RQ 2.12.0 evaluation projects under `evals/`.
- Added separate loopback Redis/Worker/probe Compose projects and random per-run credentials.
- Added self-checking PowerShell runners covering the documented comparison criteria.
- Forced RQ to use its documented JSON serializer rather than its insecure default serializer.
- Added contract coverage and updated the architecture plan before making the evidence-backed
  framework decision.
- Captured successful owner-account Docker evidence for both candidates and recorded measured idle
  deltas: Dramatiq 141 and RQ 249 commands in ten seconds.
- Added ADR-015 selecting Celery 5.6.3 from the three-candidate evidence and recorded its explicit
  owner acceptance; the runtime Worker remains unchanged.
- Updated architecture validation to keep the API Queue-neutral, reject unselected candidates and
  allow only the exact accepted Celery Redis pin when the later runtime increment adds it.

## Architecture and Design Decisions

ADR-015 is accepted and selects Celery 5.6.3 from the completed comparison. It deliberately leaves
runtime operational values and adapter adoption to a subsequent documented increment.

## Structure Preservation

All code remains under `evals/`. Application, Domain, API, Worker runtime dependencies, migrations,
hosted environment and deployable topology remain unchanged.

## Senior Review

The first review found that a `min_attempts=0` precondition could pass after an early execution had
already started. Both candidate CLIs now support `max_attempts`, and the worker-absent and delayed
preconditions require exactly zero attempts. Review of the first RQ failure traced the timeout to
the Worker idle dequeue cadence rather than silently extending the test; a bounded fixture TTL now
allows native lease cleanup without time manipulation. Exact locks, import boundaries, JSON
serialization, Compose isolation and scope boundaries pass. The accepted ADR remains constrained to
the evaluated framework/version and no runtime dependency was introduced. Senior review also found
and corrected the stale validation rule that would have rejected the accepted dependency later.

## Verification

Both Docker runners emitted PASS. Dramatiq and RQ each recovered forced Worker loss with two
attempts and one business outcome, preserved one outcome after duplicate publish and delivered the
delayed probe after the exact-zero precondition. Static and regression results are detailed in the
linked test report. The final repository verification passed 6 record tests, 73 contract tests,
18 Web tests, 143 API tests and 16 Worker tests; architecture validation passed all 22 checks.

## Remaining Risks

- Local Redis command counts cannot establish hosted quota or cost behavior.
- Outbox recovery and PostgreSQL-backed business idempotency remain owned by S1-E03/S1-E04.
- Runtime integration remains blocked on the undocumented operational contract values identified in
  ADR-015; framework/version approval itself is complete.
