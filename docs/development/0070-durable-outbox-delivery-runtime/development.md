# Development Record: 0070 Durable Outbox Delivery Runtime

- Increment ID: `0070-durable-outbox-delivery-runtime`
- Date: 2026-09-21
- Owner: Platform/Worker Engineering
- Related story: `S1-E03 — Durable Outbox Delivery Runtime`
- [Test report](./test-report.md)

## Scope

Implement the frozen, recoverable Outbox delivery path for committed TXT Parser work. Persist an
explicit delivery channel, claim due Queue events with a short PostgreSQL lease transaction,
publish the approved minimal Parser message through Celery, and acknowledge or schedule retry in a
separate transaction. Preserve at-least-once delivery and consumer idempotency. Hosted activation,
`domain_event` delivery and automatic terminal exhaustion remain excluded.

## Source Documents

- Owner-approved and frozen `0070 — Durable Outbox Delivery Runtime` contract, 2026-09-21.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), Job/Outbox, Worker and testing requirements; synced 2026-09-21.
- [Final Production Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit), PostgreSQL authority and transactional Outbox; synced 2026-09-21.
- [Engineering Implementation Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit), Worker/Outbox sequencing; synced 2026-09-21.
- [Test Strategy v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit), async failure and recovery verification; synced 2026-09-21.
- [ADR-015](../../adr/ADR-015-durable-queue-framework.md),
  [ADR-016](../../adr/ADR-016-outbox-relay-contract.md),
  [ADR-051](../../adr/ADR-051-txt-parser-consumer-recovery.md) and
  [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-7001 | Explicit routing | Persisted `delivery_channel`; exact producers use `job_queue` or `domain_event` | TC-7001, TC-7009 |
| REQ-7002 | Short crash-safe claim | `PostgresOutboxDeliveryRepository.claim_batch`; `FOR UPDATE SKIP LOCKED`; 30-second lease; commit before publish | TC-7002, TC-7003 |
| REQ-7003 | Frozen runtime bounds | Poll 2s, batch 20, lease 30s | TC-7001, TC-7002 |
| REQ-7004 | Deterministic retry | `2,4,8,16,32,60...` schedule with no terminal max-attempt state | TC-7004 |
| REQ-7005 | Unknown event fail-closed | Durable `blocked_unknown_event`, no Celery call and no hot-loop | TC-7005 |
| REQ-7006 | At-least-once recovery | Ack failure retains claim; lease expiry reclaims same Outbox ID | TC-7003, TC-7006 |
| REQ-7007 | Exact Queue mapping | `context_added.v1` to `aria.context.parse.v1`; minimal versioned envelope; SDK retry disabled | TC-7007, TC-7008 |
| REQ-7008 | Consumer idempotency | Existing PostgreSQL Job guard suppresses completed duplicate delivery | TC-7006 |
| REQ-7009 | Least privilege | Worker has column-level claim/delivery UPDATE only; no payload/route UPDATE or INSERT/DELETE | TC-7009 |
| REQ-7010 | Safe observability | Bounded claim/publish/reclaim/block events and latency/attempt metadata; payload excluded | TC-7010 |
| REQ-7011 | Existing artifact | Explicit `worker|relay` process mode; no new deployable | TC-7001, TC-7011 |
| REQ-7012 | Hosted activation gate | Railway configuration unchanged; docs state Hosted Relay remains disabled | TC-7011, TC-7012 |

## Assumptions and Clarifications

The owner froze routing, timings, deterministic backoff, unknown-event behavior, task identity,
at-least-once semantics and the complete local activation gate. The implementation does not select
a max attempt, dead-letter behavior, `domain_event` transport or hosted topology.

**Unapproved assumptions:** None

## Changes

- Added Migration 0025 with explicit channel, durable claim token/timestamps, lease-aware
  eligibility index, blocked-unknown state, DB coherence constraints and narrow Worker authority.
- Updated every existing Outbox producer to set its approved channel explicitly.
- Added provider-neutral relay Application policy and a PostgreSQL adapter whose claim transaction
  ends before Queue I/O.
- Added a Celery publisher for the single approved Parser event and registered the exact Parser task
  inside Queue Infrastructure. Celery publish retry remains disabled.
- Added explicit `python -m app.main relay` process mode to the existing Worker artifact without
  changing Railway services or commands.
- Extended the Parser's authoritative Outbox validation with the persisted channel.
- Added unit, contract, real PostgreSQL, real Redis outage/recovery, concurrent claim, lease replay,
  duplicate consumer and negative leakage tests.
- Added ADR-057 and updated the architecture, data model, Worker, migration and deployment mirrors.

## Architecture and Design Decisions

- PostgreSQL remains authoritative; Redis/Celery carries only a minimal delivery envelope.
- Claim/lease and finish/retry are separate short transactions. No transaction spans Queue I/O.
- A claim token guards every acknowledgement, retry or block transition against stale relays.
- Queue publication is at-least-once. The relay deliberately does not claim exactly-once behavior.
- Domain events are retained but excluded from the 0070 relay query and publisher mapping.
- Backoff is overflow-safe and capped before exponentiation for arbitrarily large attempt counts.
- Worker authority is column-scoped so delivery logic cannot mutate Outbox payload or routing
  identity even if compromised.

## Structure Preservation

- No new deployable, API endpoint, UI route, Queue, Provider or hosted service was added.
- Domain/Application packages import no Celery, Redis, SQLAlchemy or infrastructure types.
- All Celery/Kombu imports remain under Worker Queue Infrastructure.
- Existing modular-monolith API/Worker boundaries and the registered Worker artifact are preserved.
- Canonical repository mirrors identify their source links and synchronization date.

## Senior Review

- PASS: claim transaction commits before publish; concurrent relays cannot claim the same row.
- PASS: stale claim identity cannot acknowledge or reschedule a newer lease owner.
- PASS: publish success plus ack failure recovers the same event after lease expiry.
- PASS: Queue outage schedules the exact bounded deterministic delay and preserves durable work.
- PASS: unknown queue events are retained and blocked without hot-looping.
- PASS: only the approved Parser mapping exists; `domain_event` never reaches Celery.
- PASS: duplicate Parser delivery becomes a successful no-op after terminal completion.
- PASS: Worker privilege was tightened during review from table-wide UPDATE to exact delivery-state
  columns; payload and routing identity are not writable.
- PASS: logs exclude Outbox payload, Queue message content, customer text and transport exception
  text.
- PASS: hosted configuration remains unchanged and does not activate the Relay.

## Verification

See [test-report.md](./test-report.md). Migration 0025 was installed from an empty database into a
dedicated local PostgreSQL 16 database. Real PostgreSQL/Redis recovery tests and repository quality
gates passed. No Hosted Relay or `domain_event` delivery was activated.

## Remaining Risks

- Hosted topology, replica count and runtime activation remain a separate approved decision after
  reviewing this local evidence.
- Normal task-exception ACK/requeue and automatic Job retry/exhaustion remain governed by the
  existing deferred retry policy; 0070 adds no hidden retry.
- `domain_event` subscribers, dead-letter handling and operational unblock tooling require separate
  contracts.

**Final status:** PASS
