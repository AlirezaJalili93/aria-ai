# Aria observability

Framework-neutral trace-context and structured-event primitives shared by the API and Worker.

## Boundaries

- Accepts or generates UUID request/correlation identifiers.
- Carries one correlation identifier through versioned job and provider contexts.
- Emits JSON events from a strict allowlist; arbitrary fields and raw content are discarded.
- Adds `schema_version: "1"` to every event.
- Allows safe Auth reason/provider/timing fields and future AI provider/model/workflow/attempt,
  latency, status, error, token-count, and estimated-cost fields without prompt/response content.
- Supports explicit account/project/job enrichment; account and project identifiers may be attached
  only after the caller has completed tenant authorization.
- Contains no FastAPI, queue, provider, persistence, or domain dependency.

The HTTP middleware remains in `apps/api`; Worker and future provider adapters bind this package at their own framework boundaries.
