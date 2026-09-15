# Development Record: 0029 Outbox Relay Contract

[Test report](./test-report.md)

## Scope

- Increment ID: `0029-outbox-relay-contract`
- Story: `S1-E03 — Transactional Outbox`, partial relay contract
- Status: Completed
- Scope: provider-neutral publication of one committed Outbox event, separate published-state
  acknowledgement, recovery after acknowledgement failure, duplicate-publication evidence and safe
  structured logging.
- Explicitly deferred: Queue message envelope, Queue name, Celery/Redis/Kombu producer adapter,
  scheduler, batch selection, claim/lease, attempt mutation, retry/backoff, dead-letter and Worker
  consumer behavior.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — canonical S1-E03 acceptance; read 2026-09-05.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit?usp=drivesdk) — transactional outbox and recovery gate; read 2026-09-05.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit?usp=drivesdk) — TC-OUT-003/004/005/006 and async failure requirements; read 2026-09-05.
- [ADR-002 — Async Pipeline](../../architecture/decisions/ADR-002-async-pipeline.md)
- [ADR-013 — Jobs and Transactional Outbox Boundary](../../adr/ADR-013-jobs-outbox-persistence.md)
- [ADR-015 — Durable Queue Framework](../../adr/ADR-015-durable-queue-framework.md)
- [ADR-016 — Partial Outbox Relay Contract](../../adr/ADR-016-outbox-relay-contract.md)
- [Repository instructions](../../../AGENTS.md)

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-2901 | S1-E03; ADR-002 | `QueuePublisher` Application port; no provider import | TC-2901 |
| REQ-2902 | S1-E03; ADR-013/016 | `OutboxRelay.publish` publishes before separate `mark_published` transaction | TC-2902 |
| REQ-2903 | S1-E03; Test Master TC-OUT-005 | Mark failure leaves durable event pending for later recovery | TC-2903 |
| REQ-2904 | S1-E03; Test Master TC-OUT-004 | Same stable Outbox ID is passed again; consumer dedup remains a future contract | TC-2904 |
| REQ-2905 | S1-A04; Test Master TC-OUT-006 | Correlation/account/aggregate identifiers and attempt are logged without payload | TC-2905 |
| REQ-2906 | Owner approval 2026-09-05; ADR-016 | Queue name, transport, scheduling, batch and lease policy remain deferred | TC-2901, TC-2907 |

## Changes

- Added the provider-neutral `QueuePublisher` port to the Jobs Application boundary.
- Extended the Outbox repository port and SQLAlchemy adapter with explicit `mark_published`.
- Added `OutboxRelay` for one-event publication followed by a separate PostgreSQL acknowledgement.
- Preserved `pending` on publisher or acknowledgement failure; no retry/backoff or attempt mutation
  was invented.
- Added safe Outbox lifecycle events: `outbox.relay_started`, `outbox.publish_succeeded`,
  `outbox.publish_failed`, `outbox.mark_published_failed` and `outbox.republished`.
- Extended the structured-log allowlist only with UUID-safe Outbox/aggregate identifiers and a safe
  aggregate type.
- Added ADR-016 and updated the queue evaluation plan/ADR index.
- Added application, API, contract and logging tests before declaring completion.

## Structure Preservation

- Domain remains framework-free and unchanged.
- Application owns the relay orchestration and imports no Celery, Redis, Kombu, FastAPI or SQLAlchemy.
- Infrastructure owns the PostgreSQL mark operation; no Queue transport was added to API.
- The existing transactional Job + Outbox write remains a single Application-owned commit.
- No migration, schema field, Queue name, scheduler or deployable service was added.
- Existing API/Worker/Web module boundaries and documentation structure remain intact.

## Senior Review

- PASS: publisher invocation occurs before the acknowledgement transaction.
- PASS: acknowledgement failure is observable and does not convert the event to `published`.
- PASS: duplicate publication retains the stable event ID and does not claim consumer-side deduplication.
- PASS: log fields are allowlisted and payload/body values are excluded.
- PASS: API remains queue-framework neutral; Celery remains Worker-only under ADR-015.
- PASS: deferred producer/consumer decisions are explicit in ADR-016 rather than inferred.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The owner approved the partial contract on 2026-09-05. Deferred Queue producer/consumer details are
explicitly excluded from this increment and are not silently selected by the implementation.

## Verification

See [test-report.md](./test-report.md). Focused relay tests, API tests, contract tests, lint, type
checking, architecture validation and the repository quality gates passed. Warnings were limited to
existing Windows cache permissions and the existing Starlette/httpx deprecation warning.

## Remaining Risks

- A future accepted Queue/Worker contract must define the message envelope, producer adapter, Queue
  name, scheduling, batch/claim/lease and retry policy before deployment wiring.
- Consumer idempotency and duplicate business-side-effect prevention remain S1-E04.
- No hosted Queue or Docker relay runtime smoke was claimed by this partial contract.

**Final status:** PASS
