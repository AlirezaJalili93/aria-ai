# ADR-016: Partial Transactional Outbox Relay Contract

- Status: Accepted
- Date: 2026-09-05
- Scope: S1-E03 partial relay contract

## Context

The Jobs/Outbox persistence boundary is committed in PostgreSQL before any external queue I/O.
The approved Sprint 1 contract requires recoverable publication and at-least-once delivery, but it
does not yet select a Queue name, message envelope, producer transport, Celery/Redis adapter,
scheduler, batch size or claim/lease policy.

## Decision

- Application exposes a provider-neutral `QueuePublisher` port whose input is the committed
  `OutboxEvent` domain object.
- The partial relay publishes one event through that port, then opens a separate PostgreSQL unit of
  work to mark the event `published`.
- If publication succeeds but marking fails, the durable event remains `pending`; a later invocation
  may publish the same stable event ID again.
- Duplicate publication is an accepted at-least-once consequence. Consumer-side idempotency using the
  stable Outbox event ID is required in the future Worker/consumer contract.
- Relay logs use only event/aggregate identifiers, account/correlation context, attempt and duration;
  the event payload is never logged.

## Deferred boundaries

Queue message shape, Queue name, framework-specific producer wiring, scheduling, batch selection,
claim/lease semantics, attempt mutation, retry/backoff and dead-letter behavior remain unapproved and
are not implemented here. A future Queue/Worker ADR must define them before infrastructure wiring.

## Consequences

- The API remains independent of Celery, Redis and Kombu.
- Publication and acknowledgement cannot be an accidental dual write in the request transaction.
- Recovery is explicit and testable without inventing a transport contract.
- Until the deferred producer contract is accepted, this increment is a partial relay contract and not
  a deployable Queue publisher.
