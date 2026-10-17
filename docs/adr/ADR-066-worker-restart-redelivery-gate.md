# ADR-066 — Controlled Worker Restart and Broker Redelivery Gate

- Status: Accepted
- Date: 2026-09-28
- Decision owner: Product and Engineering
- Extends: ADR-015, ADR-057, ADR-058 and ADR-065

## Context

Sprint 1 E2E-05 and S1-E02 require an in-flight Job to survive Worker restart under an
at-least-once Queue. The selected Celery boundary already requires late acknowledgement,
Worker-loss rejection and prefetch-one behavior, while PostgreSQL remains the Job source of truth
and a session advisory lock suppresses concurrent execution. The remaining gate must prove these
pieces together in the product runtime without crossing the separately deferred post-Provider
recovery boundary.

## Decision

### Controlled boundary

- The gate exercises AI-01 Context Structuring only through the real HTTP command, transactional
  Outbox, Relay, Celery/Redis delivery, Worker consumer and PostgreSQL finalization boundaries.
- Only a versioned synthetic fixture and the deterministic Fake Provider are allowed. Customer
  content, real or paid Providers, Hosted activation and production orchestration are prohibited.
- The test uses a throwaway PostgreSQL database and isolated local Redis Queue.

### Deterministic crash checkpoint

Worker #1 is hard-killed only after all of the following are true:

1. `JobExecutionGuard` acquired the Job advisory lock;
2. the same Job is durably `running`;
3. the Provider boundary has not been entered;
4. no `provider_attempt_id` or UsageRecord exists.

The checkpoint is an explicit test-only failpoint at the boundary after Job preparation and before
AI invocation. Timing-only sleeps are not accepted as proof of the checkpoint. The failpoint is not
composed into Hosted or production Worker runtime.

### Redelivery and recovery

- Celery automatic task retry remains disabled. Recovery comes only from broker redelivery of the
  unacknowledged message under the accepted late-acknowledgement and Worker-loss behavior.
- Worker #1 process death closes its PostgreSQL session and releases the advisory lock. Worker #2
  must reacquire the same recoverable `running` Job. A second Worker cannot acquire the Job while
  the first session still holds the lock.
- Redelivery retains the same `outbox_event_id` and `job_id`; it creates no new Job, Outbox event,
  Source or Context Version.
- Worker #2 invokes the Fake Provider exactly once and atomically finalizes Context Items, one
  Context Version and the same Job as `succeeded`.

### Required assertions

Before the hard kill, `provider_invocations=0` and `usage_records=0`. After recovery,
`provider_invocations=1`, `usage_records=1`, the original Job and Outbox identities are unchanged,
exactly one final Context Version is committed and duplicate business effects are zero.

Crashes during Provider execution, after Provider success but before durable persistence, or around
paid-provider accounting remain outside this decision and require separate recovery contracts.

## Consequences

- The gate proves TC-JOB-008 and Sprint E2E-05 at the approved pre-Provider checkpoint using the
  actual Queue runtime rather than direct consumer invocation.
- No product retry count, backoff, dead-letter policy, new Job state, schema or public endpoint is
  introduced.
- Failure of this gate blocks the Sprint Queue restart recovery claim but does not enable Hosted
  AI processing.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-E02, E2E-05 and Sprint DoD; reread 2026-09-28.
- [Test Strategy v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit), TC-JOB-008 and async recovery; reread 2026-09-28.
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit), Durable Async Worker and Job source-of-truth rules; reread 2026-09-28.
- Owner-approved frozen 0080 contract, 2026-09-28.

**Unapproved assumptions:** None
