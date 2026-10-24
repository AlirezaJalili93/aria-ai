# ADR-015: Durable Queue Framework

- Status: Accepted
- Date: 2026-09-05
- Accepted by: Product owner response `ادامه بده` to the explicit ADR-015 approval request on
  2026-09-05.
- Canonical references: Sprint 1 Technical Backlog S1-E02/E2E-05, Final System Architecture v2.0,
  Accepted ADR Pack ADR-007 through ADR-010, and Sprint 0 ADR Register Queue spike criteria; synced
  from Google Drive 2026-09-05.
- Evidence: `docs/architecture/durable-queue-evaluation-plan.md` and development records 0026/0027.

## Context

ADR-004 deferred the documented Celery/Dramatiq/RQ decision until a Linux/Redis spike measured
worker absence, forced Worker loss, duplicate delivery, scheduling and idle command activity. The
current hosted Redis-compatible Queue is constrained by a free-service budget, so command activity
is a relevant selection signal. PostgreSQL Jobs and Outbox remain the durable Source of Truth under
ADR-013; the Queue is delivery infrastructure rather than business state.

All three exact candidates passed the local Docker recovery probes with one idempotently committed
outcome. Their ten-second idle Redis command deltas were Celery 5.6.3=`36`, Dramatiq 2.2.1=`141`,
and RQ 2.12.0=`249`. RQ required explicit JSON serialization, an opt-in retry, and a bounded idle
dequeue cadence before its approximately 61-second abandoned-job lease could be reclaimed. Celery
and Dramatiq recovered after their five-second experiment visibility/heartbeat fixtures.

## Decision

Select Celery 5.6.3 with its Redis transport as the S1-E02 Worker Queue framework.

This decision selects only the framework and exact evaluated version. Product execution timeout,
visibility duration, retry count/backoff, exhausted-message policy, Outbox relay cadence and hosted
capacity remain unapproved until their owning contracts are documented. Runtime adoption must keep
JSON-only serialization, late acknowledgement, Worker-loss rejection and prefetch-one semantics
demonstrated by the candidate; Application handlers remain idempotent because delivery is at least
once.

## Evidence-Based Rationale

- All mandatory local durability probes passed.
- Celery produced the lowest measured idle command delta under the same ten-second observation.
- The current Redis-compatible hosting provider publishes an explicit Celery integration path.
- The evaluated configuration exposes acknowledgement, Worker-loss and prefetch behavior directly.
- Selecting it does not change PostgreSQL/Outbox transaction ownership or Domain boundaries.

## Consequences

- Increment 0028 adds the exact Celery dependency and Infrastructure Queue adapter while preserving
  the operational approval boundary.
- S1-E03 must publish Outbox events recoverably; direct API-to-broker dual writes remain forbidden.
- S1-E04 must enforce bounded retries and PostgreSQL-backed idempotency beyond the evaluation probe.
- Hosted Upstash command/quota evidence remains a deployment gate; the local delta is not a cost
  guarantee.

## Alternatives Not Selected

- Dramatiq 2.2.1 passed all probes and has a smaller isolated dependency graph, but used 141 idle
  Redis commands in the measured window versus Celery's 36.
- RQ 2.12.0 passed after its native abandoned-job recovery was allowed to run, but requires explicit
  JSON replacement for its documented insecure default serializer and recorded the highest idle
  command delta under the bounded recovery fixture.
- Redis Pub/Sub remains rejected by accepted ADR-007 because it is not a durable job Queue.

## Approval Boundary

The owner accepted the Celery 5.6.3 framework/version decision, and increment 0028 implements that
framework boundary. This acceptance does not approve
product execution timeout, visibility duration, retry count/backoff, exhausted-message policy,
Outbox relay cadence, hosted capacity or deployment changes; those values still require their own
documented contracts.
