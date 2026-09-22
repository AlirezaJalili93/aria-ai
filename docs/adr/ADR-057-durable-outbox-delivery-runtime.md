# ADR-057 — Durable Outbox Delivery Runtime

- Status: Accepted
- Date: 2026-09-21
- Decision owner: Product and Engineering
- Extends: ADR-015, ADR-016 and ADR-051

## Context

The persisted Outbox and controlled TXT Parser consumer existed, but no continuous, crash-safe
delivery path connected committed parser events to the selected Celery/Redis Queue. The canonical
architecture requires PostgreSQL to remain authoritative, transactional Outbox publication and
recoverable at-least-once delivery. Hosted activation must wait until recovery evidence passes.

## Decision

### Explicit routing

- Every Outbox row persists `delivery_channel = job_queue | domain_event`.
- `context_added.v1` uses `job_queue` and maps only to Celery task `aria.context.parse.v1`.
- `requirement.conflict_detected` uses `domain_event`; 0070 never publishes that channel to Celery.
- Runtime routing never infers a channel from an event name. An unknown `job_queue` event becomes
  `blocked_unknown_event`, remains durable and is removed from automatic eligibility.

### Claim and lease

- One relay cycle claims at most 20 eligible rows with `FOR UPDATE SKIP LOCKED`.
- The claim transaction records a generated `claim_id`, `claimed_at`, 30-second `lease_until` and
  increments `attempt_count`, then commits before any network publication begins.
- Only pending, due `job_queue` rows with no lease or an expired lease are eligible.
- Completion operations require both event and claim identity. A stale relay cannot acknowledge,
  reschedule or block a claim now owned by another relay.

### Delivery and recovery

- Delivery is at-least-once. A successful publish followed by failed PostgreSQL acknowledgement
  intentionally leaves the claim for replay after lease expiry.
- Publish failure clears the claim and schedules deterministic backoff:
  `min(60s, 2s * 2^(delivery_attempt-1))`, producing `2,4,8,16,32,60...` seconds.
- No maximum attempt or automatic terminal failure exists in 0070.
- Relay polling is every two seconds. The existing Worker artifact supports explicit process mode
  `relay`; no new deployable is introduced.
- Celery SDK publish retry is disabled. One relay attempt represents one transport invocation.
- The Parser consumer retains the existing PostgreSQL JobExecutionGuard and handles duplicate
  delivery as an idempotent no-op or recovery of the same Job/Source Version.

### Observability and activation

The relay emits bounded lifecycle events for start, claim, reclaimed lease, publication,
publication failure, acknowledgement failure, claim failure and blocked unknown event. Logs may
contain Outbox/aggregate identifiers, event type, attempt and delivery latency. They never contain
payload or customer content. Identifiers are not metric labels.

Hosted Relay activation remains disabled until local unit/contract tests, concurrent claim,
claim-commit visibility, crash/restart lease recovery, Redis outage/recovery, PostgreSQL
transaction/recovery and duplicate-consumer idempotency all pass. `domain_event` delivery remains
deferred.

## Consequences

- A Queue outage cannot lose committed work or produce a hot loop.
- More than one relay can run without claiming the same eligible event.
- Exactly-once publication is not claimed; duplicate suppression belongs to the idempotent
  consumer and business write invariants.
- `aria_worker` gains only column-scoped `UPDATE` for delivery state/attempt/claim timestamps in
  addition to existing `SELECT`; it cannot update payload/routing identity and still has no Outbox
  INSERT/DELETE authority.
- Hosted deployment needs an explicit, separately approved `relay` process activation after the
  recovery gate passes.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), Job/Outbox, Worker and testing requirements; synced 2026-09-21.
- [Final Production Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit), PostgreSQL authority and transactional Outbox; synced 2026-09-21.
- [Engineering Implementation Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit), Worker and Outbox sequencing; synced 2026-09-21.
- [Test Strategy v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit), async failure and recovery verification; synced 2026-09-21.
- Owner-approved frozen `0070 — Durable Outbox Delivery Runtime` contract, 2026-09-21.

**Unapproved assumptions:** None
