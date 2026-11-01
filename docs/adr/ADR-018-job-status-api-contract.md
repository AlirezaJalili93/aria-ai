# ADR-018 — Job Status API Contract

- Status: Accepted for Sprint 1 / S1-E05
- Date: 2026-09-05
- Scope: Read-only tenant-scoped Job status endpoint

## Decision

Expose `GET /api/v1/jobs/{job_id}` as the client-facing source of truth for asynchronous Job
status. The endpoint requires the existing Bearer JWT and `X-Account-ID` tenant context. A Job
that is missing or belongs to another Account returns the existing safe `404 RESOURCE_NOT_FOUND`
contract.

The public response is deliberately limited to:

```json
{
  "data": {
    "id": "uuid",
    "job_type": "string",
    "status": "queued|running|succeeded|failed|cancelled",
    "progress_stage": "string|null",
    "retryable": false,
    "error": null
  },
  "meta": {"request_id": "uuid"}
}
```

For a failed Job, `error` contains the persisted sanitized `code` and `detail` only. Persistence
and operational fields such as payload references, attempts, correlation IDs and timestamps are
not public API fields.

## Boundaries

- `job_type` is canonical; `task_type` is not used by this API.
- `progress_stage` is nullable because the approved Job persistence model has no stage field yet;
  no new column or stage taxonomy is introduced here.
- Retry classification is deferred. The response includes `retryable`; this increment returns
  `false` until an approved retry classification exists.
- PostgreSQL remains the source of truth and the repository query is Account-scoped.
- SSE is not introduced by this decision. Polling fallback remains the documented client strategy;
  frontend polling and any SSE enhancement require their own UI/transport contract.

## Consequences

The API can safely report queued/running/completed/failed state without exposing private Job
payloads or tenant identifiers. Future retry classification, progress persistence and SSE can be
added without expanding this public contract implicitly.
