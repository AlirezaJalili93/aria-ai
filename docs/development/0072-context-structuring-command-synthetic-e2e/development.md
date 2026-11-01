# Development Record: 0072 Context Structuring Command API & Controlled Synthetic E2E

- Increment ID: `0072-context-structuring-command-synthetic-e2e`
- Date: 2026-09-22
- Owner: Backend/Platform Engineering
- Related story: Sprint 1 Context Structuring command and controlled E2E activation
- [Test report](./test-report.md)
- [ADR-059](../../adr/ADR-059-context-structuring-command-synthetic-e2e.md)

## Scope

Implement the frozen public HTTP command for explicit Context Structuring and prove the controlled
synthetic path through the existing durable Outbox and Worker foundations. Keep the server-side
feature disabled by default and prohibit Hosted activation, customer content, real Providers,
Primary/Fallback selection and Parser-to-AI chaining.

## Source Documents

- Owner-approved and frozen `0072 — Context Structuring Command API & Controlled Synthetic E2E`
  contract, 2026-09-21.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), AI-01 and mandatory E2E flow; synchronized 2026-09-21.
- [API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit), Context Structuring command; synchronized 2026-09-21.
- [Sprint 1 Acceptance & Demo Script v1.0](https://docs.google.com/document/d/1cNO4P5hBIzgQAvNVAnOdfI84IyTQj8UXxdN9GfGvb1Y/edit), controlled deterministic demo mode; synchronized 2026-09-21.
- [ADR-058](../../adr/ADR-058-context-structuring-job-runtime-foundation.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-7201 | Frozen 0072 HTTP contract | `context_structuring.py`; OpenAPI accepted response | TC-7201, TC-7202 |
| REQ-7202 | Project before idempotency; replay before readiness/active guard | `ScheduleContextStructuringUseCase.execute` | TC-7203, TC-7204 |
| REQ-7203 | Frozen error mapping and safe tenant 404 | Router mapping plus declared API error handlers | TC-7203, TC-7205 |
| REQ-7204 | Server flag default-off/fail-closed | `ApiSettings.context_structuring_enabled`; API composition | TC-7206 |
| REQ-7205 | Synthetic-only invariant independent of flag | `SyntheticContextStructuringAuthorizer`; deny-all normal composition | TC-7207 |
| REQ-7206 | HTTP → Outbox → Celery → Worker → atomic success | Controlled two-process E2E harness | TC-7208 |
| REQ-7207 | No Hosted/customer/real-provider activation | Hosted configuration rejection, static contract and ADR-059 | TC-7209 |
| REQ-7208 | Test isolation must not reset a general database | Dedicated `aria_0072_test...` database guard | TC-7210 |
| REQ-7209 | Repository quality and security gates remain green | Root scripts and development records | TC-7211 |

## Assumptions and Clarifications

The owner froze the exact command, validation order, membership rules, status/error semantics,
synthetic-only boundary and E2E gate. Implementation does not infer Provider promotion or customer
data authorization from the feature flag.

**Unapproved assumptions:** None

## Changes

- Added `POST /api/v1/projects/{project_id}/context-structuring` with an exactly empty body,
  mandatory tenant/idempotency headers, exact `202 {job_id,status_url}` response and frozen errors.
- Added declared `CONTEXT_STRUCTURING_IN_PROGRESS` and `CONTEXT_READY_SOURCE_REQUIRED` handlers.
- Reordered scheduling so the tenant-scoped Project is resolved before idempotency and exact replay
  precedes Source readiness and active-Job checks.
- Added a provider-neutral synthetic Project authorizer. Normal API composition installs deny-all;
  controlled tests inject an explicit Account/Project allowlist.
- Added `CONTEXT_STRUCTURING_ENABLED=false`; Staging and Production reject attempts to enable it.
- Updated OpenAPI and API/Worker/Railway environment documentation without enabling Hosted work.
- Added API/application/PostgreSQL/static tests for command validation, replay, safe 404,
  cross-tenant ordering, error mapping, concurrency and synthetic boundaries.
- Added a controlled E2E harness covering HTTP, PostgreSQL Outbox, durable Relay, Celery mapping,
  Worker consumer, deterministic Fake Provider and atomic final state.
- Added a destructive-test guard: the harness accepts only a dedicated database named
  `aria_0072_test...` before any migration or fixture reset.

## Architecture and Design Decisions

- ADR-059 extends ADR-057/058 and records that this is an API/orchestration proof, not Product AI
  acceptance or Hosted activation.
- The API remains transport-only; scheduling rules and idempotency ordering remain in Application.
- Infrastructure details remain behind the existing Unit of Work, Relay, Celery publisher and
  Worker adapters.
- The feature flag controls exposure only. Synthetic authorization is a separate fail-closed
  Application boundary and cannot be bypassed by enabling the flag.
- The Queue envelope stays identifier-only. The Worker resolves authoritative state from
  PostgreSQL and no Context/customer payload enters Outbox or Queue messages.
- No schema migration was required; the frozen 0071 Job/Outbox/runtime schema is reused.

## Structure Preservation

- Modular-monolith boundaries remain API Router → Application Use Case/Ports → Infrastructure UoW.
- Domain/Application code imports no FastAPI, Celery, Provider SDK or storage implementation.
- No new deployable service, Provider selection, automatic Queue retry or Parser-to-AI chaining
  was added.
- Existing `/jobs/{job_id}` remains the status query; no duplicate status or debug endpoint exists.
- Hosted Worker task registration remains disabled and Railway configuration stays fail-closed.
- The OpenAPI addition is limited to the approved command and exact response schema.

## Senior Review

- Verified safe 404 occurs without an out-of-tenant existence probe and before idempotency access.
- Verified exact replay returns the stored Job before readiness/active-Job checks, while a new key
  is rejected by the database-enforced active-Job guard.
- Verified normal runtime composition cannot authorize any synthetic Project and Hosted settings
  reject feature activation.
- Verified E2E message identity preserves both `job_id` and `outbox_event_id` through Relay/Celery.
- Verified logs do not contain the synthetic fixture marker and no Provider credential/model
  appears in API composition or the controlled harness.
- Found and removed a credential-shaped test URL that correctly triggered the Secret scanner.
- Found that the first E2E harness accepted a general `TEST_DATABASE_URL`; added a mandatory
  dedicated-database name guard and reran the complete migration/E2E path on
  `aria_0072_test_20260922`.
- No High/Critical issue remains in the approved 0072 scope.

## Verification

See [test-report.md](./test-report.md). API, Worker, Web, contract, Eval, PostgreSQL E2E, lint,
typecheck, build, dependency, secret and architecture/development-record gates pass.

## Remaining Risks

- Real-provider quality, customer-content execution, Provider promotion/fallback, entitlement,
  quota and paid-call post-response recovery remain explicitly deferred.
- Hosted AI activation and Parser-to-AI chaining remain prohibited.
- The Python test stack emits an upstream Starlette/httpx deprecation warning; it does not affect
  the frozen contract and requires a separately approved dependency update.
- The controlled harness intentionally resets only its explicitly named disposable test database;
  callers must provision that dedicated database before execution.

**Final status:** PASS
