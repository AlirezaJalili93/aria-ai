# ADR-059 — Context Structuring Command API and Controlled Synthetic E2E

- Status: Accepted
- Date: 2026-09-21
- Decision owner: Product and Engineering
- Extends: ADR-057 and ADR-058

## Context

ADR-058 proved the internal AI-01 Job runtime while deliberately withholding a public command and
Hosted activation. Sprint 1 API and acceptance baselines require an explicit asynchronous command
and end-to-end evidence, but real Provider promotion, customer data review, paid-call recovery and
Hosted AI activation remain unapproved.

## Decision

- Expose `POST /api/v1/projects/{project_id}/context-structuring` with Bearer JWT,
  `X-Account-ID`, active Membership, mandatory `Idempotency-Key` and an exactly empty body.
- Return exactly `202 {job_id,status_url}`. Any body bytes, including `{}`, fail with
  `422 VALIDATION_FAILED`.
- Resolve the tenant-scoped Project before idempotency. Exact replay then returns the original Job
  before Source readiness or active-Job checks. New commands require a ready Source and the
  PostgreSQL active-Job guard.
- Preserve safe 404 and the frozen `IDEMPOTENCY_CONFLICT`,
  `CONTEXT_STRUCTURING_IN_PROGRESS`, `CONTEXT_READY_SOURCE_REQUIRED` and
  `FEATURE_NOT_ENABLED` semantics.
- Add a server-side `CONTEXT_STRUCTURING_ENABLED` flag that defaults false and cannot be enabled in
  Staging or Production.
- Treat the flag only as exposure control. A separate Application authorizer must explicitly allow
  an Account/Project pair as a synthetic fixture. Normal runtime composition installs deny-all;
  only controlled test composition receives an in-memory allowlist.
- Keep Worker Hosted task composition, real OpenAI/Gemini, runtime Primary/Fallback, customer
  content and Parser-to-AI chaining disabled.

## E2E Evidence

The controlled fixture must prove HTTP command → atomic Job/Outbox → durable Relay → exact Celery
message → AI-01 Worker → deterministic Fake Provider → validation → atomic Context Items, Project
Context Version and Job success. This evidence does not constitute Product AI quality acceptance.

## Consequences

- The public HTTP shape and orchestration can regress in CI without expanding data or cost risk.
- Merely setting the feature flag cannot authorize a Project or enable Hosted processing.
- Real-provider evaluation, customer content, entitlement/quota, paid-call recovery and Hosted
  activation still require independent accepted gates.

## Sources

- Owner-approved frozen `0072` contract, 2026-09-21.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), synchronized 2026-09-21.
- [API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit), synchronized 2026-09-21.
- [Sprint 1 Acceptance & Demo Script v1.0](https://docs.google.com/document/d/1cNO4P5hBIzgQAvNVAnOdfI84IyTQj8UXxdN9GfGvb1Y/edit), synchronized 2026-09-21.

**Unapproved assumptions:** None
