# ADR-058 — Context Structuring Job Runtime Foundation

- Status: Accepted
- Date: 2026-09-21
- Decision owner: Product and Engineering
- Extends: ADR-016, ADR-017, ADR-026, ADR-027 and ADR-057

## Context

The provider-neutral AI-01 Context Structuring use case and deterministic validation/repair
pipeline already existed, but it had no approved durable Job runtime. The next increment needs to
prove orchestration, transactionality and duplicate suppression without selecting a production
Provider, exposing a public command or sending customer content to AI.

## Decision

### Activation boundary

- AI-01 is triggered explicitly; Parser-to-AI chaining is prohibited.
- The future public command contract is `POST /api/v1/projects/{project_id}/context-structuring`
  with an empty body and mandatory `Idempotency-Key`, but the Public Endpoint is Disabled in 0071.
- Hosted activation is disabled. No runtime Primary or Fallback is selected.
- Only `SyntheticContextStructuringAI` may be used for 0071 verification. Customer content and paid
  Provider calls are prohibited; synthetic test fixtures are the only approved input.

### Durable scheduling and delivery

- The internal scheduler persists `job_type=context_structuring` and
  `context.structuring_requested.v1` in one transaction with the idempotency reservation.
- Exact replay returns the same `job_id` and creates no second Job or Outbox event. Conflicting key
  reuse fails with `IDEMPOTENCY_CONFLICT`.
- A partial unique PostgreSQL index permits at most one `queued|running` Context Structuring Job per
  Project, closing concurrent check-then-insert races.
- `delivery_channel=job_queue` maps to Celery task `aria.context.structure.v1`.
- The Queue envelope contains only `message_version`, `outbox_event_id` and `job_id`. Project IDs,
  context, prompts and customer payload are excluded. The Worker resolves all authority from
  PostgreSQL using `job_id`.
- Queue-level automatic retry is disabled.

### Execution and recovery

- The shared PostgreSQL advisory Job guard suppresses concurrent or completed duplicate delivery.
- The Worker snapshots only latest ready Source Versions in the Job's Account and Project, then
  invokes the deterministic synthetic adapter.
- Context Item writes, Project `current_context_version` advancement and Job success finalization
  commit in one PostgreSQL transaction.
- A finalization/commit failure rolls back Context and Project changes, leaves the same Job
  recoverable, and releases the execution guard. Re-execution is approved only for the Fake,
  synthetic 0071 boundary.
- Real or paid Provider re-invocation after an ambiguous post-response persistence failure is not
  authorized. It requires a separately frozen AI Invocation Recovery Boundary.

### Authority and observability

- `aria_worker` may select Projects, update only `current_context_version`, and insert AI-created
  Context Items. RLS remains enabled and API/Data API roles receive no new authority.
- Logs contain bounded Job/Tenant identifiers and safe reason codes only. Source text, generated
  content, prompts, Provider output and Queue payload are excluded.

## Consequences

- AI-01 orchestration and atomicity can be exercised locally without production Provider risk.
- This increment is a runtime foundation, not a real MVP Staging AI runtime.
- Public API composition, hosted task registration, entitlements/quota, production Provider
  promotion and paid-call recovery remain deferred.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), AI-01/Worker sequencing; synced 2026-09-21.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), provider-neutral AI-01 flow and validation gates; synced 2026-09-21.
- [Final Production Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit), PostgreSQL authority and Worker boundaries; synced 2026-09-21.
- Owner-approved frozen `0071 — Context Structuring Job Runtime Foundation` contract,
  2026-09-21.

**Unapproved assumptions:** None
