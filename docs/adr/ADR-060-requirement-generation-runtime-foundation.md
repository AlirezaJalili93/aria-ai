# ADR-060: Requirement Generation Runtime Foundation

- **Status:** Accepted
- **Date:** 2026-09-22
- **Increment:** 0073 / S1-I02 runtime foundation

## Context

ADR-031 defines the provider-neutral AI-02 Requirement Extraction use case, but deliberately
deferred its durable Job, Outbox, Queue and Worker runtime. The approved 0073 contract authorizes
only an explicit internal trigger and a deterministic synthetic execution path. A public trigger,
AI-01 chaining, paid providers, customer content and hosted activation are not approved.

## Decision

- The canonical Job type is `requirement_generation`.
- The canonical Outbox event is `requirement.generation_requested.v1`, with
  `delivery_channel=job_queue`.
- The canonical Celery task identity is `aria.requirements.generate.v1`.
- Queue messages contain exactly `message_version`, `outbox_event_id` and `job_id`.
- A Job is bound at scheduling time to one explicit `context_version` and the exact sorted
  `(context_item_id, updated_at)` revision vector required by ADR-031.
- The Worker resolves all Context and Tenant state from PostgreSQL using `job_id`; neither Context
  nor customer text is persisted in Outbox or Queue envelopes.
- Requirement writes, provenance merge, conflict Domain Events and the Job success transition are
  finalized in one PostgreSQL transaction.
- Delivery is at-least-once. The Job execution guard suppresses concurrent/completed duplicates,
  while ADR-031 merge rules prevent duplicate committed Requirements.
- A persistence interruption keeps the same logical Job recoverable. Queue automatic retry is
  disabled; recovery is controlled and uses the same Job.
- The only adapter approved in 0073 is a deterministic Fake Provider over explicitly authorized
  synthetic fixtures. It is not registered in the hosted Worker composition.

## Explicitly Deferred

- Public HTTP trigger or API contract.
- Automatic AI-01 to AI-02 chaining.
- Real provider, paid invocation, customer content, Primary/Fallback routing or hosted activation.
- Queue-level automatic retry and production post-provider recovery semantics.

## Consequences

The complete internal transport and transaction boundary can be tested without making Product AI
available. A later activation decision must add a separate gate; enabling an environment flag or
registering a task is not implied by this ADR.
