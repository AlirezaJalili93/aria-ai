# Development Record: Celery Worker Runtime

- Increment ID: `0028-celery-worker-runtime`
- Date: 2026-09-05
- Owner: Platform Engineering
- Related plan/issue: S1-E02
- [Test report](./test-report.md)

## Scope

Adopt the accepted Celery 5.6.3 Redis transport in the existing Worker deployable. The runtime must
use JSON-only serialization, late acknowledgement, Worker-loss rejection, prefetch one, no Celery
result backend, and explicit Queue name, visibility duration and concurrency configuration without
defaults. Product task timeout, retry/backoff, exhausted-message handling, Outbox publication and
business task handlers remain outside this increment.

## Source Documents

- Product owner response `ادامه بده` on 2026-09-05 approving the proposed S1-E02/S1-E04 split.
- Google Drive `Aria AI — Sprint 1 Technical Backlog v1.0`, S1-E02 and E2E-05; synced 2026-09-05.
- Google Drive `Aria AI — Final System Architecture v2.0`, Durable Queue and Worker boundaries;
  synced 2026-09-05.
- Google Drive `13 — Aria AI — Accepted ADR Pack v1.0`, ADR-007 through ADR-010; synced
  2026-09-05.
- Repository [ADR-015](../../adr/ADR-015-durable-queue-framework.md) and
  [evaluation plan](../../architecture/durable-queue-evaluation-plan.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-160 | ADR-015 | Exact Celery 5.6.3 Redis dependency in Worker only | TC-2801 |
| REQ-161 | Owner-approved S1-E02 split | Required Queue name, visibility and concurrency with no defaults | TC-2802 |
| REQ-162 | ADR-007/009; ADR-015 | JSON-only, late ack, reject on Worker loss and prefetch one | TC-2803 |
| REQ-163 | ADR-010; owner approval | Disable Celery result backend; PostgreSQL Job state remains canonical | TC-2804 |
| REQ-164 | Architecture v2 | Composition root invokes the Infrastructure adapter; API remains Queue-neutral | TC-2805 |
| REQ-165 | Owner-approved scope boundary | No product timeout, retry/backoff, exhausted policy or business task handler | TC-2806 |

## Assumptions and Clarifications

The owner approved required configuration without defaults and deferred product execution timeout,
retry/backoff and exhausted-message policy to S1-E04. The existing Worker deployable and Railway
topology remain unchanged.

**Unapproved assumptions:** None

## Changes

- Added exact `celery[redis]==5.6.3` to the Worker and regenerated `apps/worker/uv.lock`.
- Added provider-neutral required Queue runtime settings for broker URL, Queue name, visibility
  duration and Worker concurrency; no repository defaults are provided.
- Added the Celery Infrastructure adapter with JSON-only serialization, late acknowledgement,
  Worker-loss rejection, prefetch one and disabled result backend.
- Updated the Worker composition root, Railway runtime contract, `.env.example` and Worker-facing
  documentation. No API Queue dependency or deployable topology was added.
- Added contract and unit coverage before runtime implementation.

## Architecture and Design Decisions

- ADR-015 remains the framework/version authority; this increment implements, but does not broaden,
  that decision.
- Required values are validated at Worker startup. Missing values fail closed rather than inheriting
  Celery or repository defaults.
- PostgreSQL Job state remains canonical; Celery result storage is disabled.
- Product execution timeout, retry/backoff, exhausted-message handling, Outbox publication and
  business task wrappers remain deferred to S1-E04/E03.

## Structure Preservation

The existing `web`/`api`/`worker` deployable topology, Railway files, API dependency set and
Domain/Application boundaries are preserved. Celery is imported only by
`apps/worker/app/infrastructure/queue/celery_runtime.py`; the composition root invokes the adapter.
No task handler or new service was introduced.

## Senior Review

- High: An initial validator would have rejected the accepted Celery pin; it was corrected to keep
  API Queue-neutral, reject Dramatiq/RQ and allow only exact Celery 5.6.3.
- Medium: Railway documentation initially placed Queue runtime variables under API; review moved
  them to Worker only.
- Medium: Startup configuration initially used a truthy dataclass default; review removed that
  default so `queue_adapter_configured=true` is only produced after explicit validation.
- No unresolved actionable finding remains in this increment.

## Verification

The final test report records the targeted contract, Worker lint/typecheck/tests, full `npm test`,
`npm run validate` and `git diff --check` results.

## Remaining Risks

- Owner-account Docker image smoke was not rerun in this session after the adapter change because the
  escalated Docker build approval was unavailable; local Celery configuration and all repository
  gates pass. The existing isolated Docker durability evidence remains recorded in increments 0026
  and 0027.
- S1-E03 Outbox publication and S1-E04 task timeout/retry/idempotency policies remain required before
  product jobs are enabled.
