# Development Record: 0060 — Operational Dashboard

- **Status:** COMPLETE
- **Increment:** S1-L02
- **Source sync date:** 2026-09-13
- [Test report](./test-report.md)

## Scope

Implement the approved Operational Dashboard baseline: staging-only direct OTLP/HTTP metrics,
bounded and fail-open instrumentation, D2/D3/D4 source-controlled Grafana dashboards, canonical
PostgreSQL Job/Outbox health projections, private query-driven AI cost summaries, and the
least-privilege `aria_observer` role. Production Collector/Alloy topology, Provider selection,
new alerts and transport-derived canonical queue depth remain deferred.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L02; revision `ANLCKQlujALNdyJZbNLOedCGxjlG8UwcE_pkF1cT3bEgoVASWO7u08ikQ51FIfnZfHk9DV_8iMg67AayWjRPBbEjFROHXn7_gAUAEruNFw`; synchronized 2026-09-13
- [Observability & Incident Response Runbook](https://docs.google.com/document/d/1oze9K7tyvmAEOYK5Ddt1LyzOcGPe_7Ru28JE23g2xPE/edit) — D2/D3/D4 and cardinality baseline; revision `ANLCKQmGCQ61piahwzQBWlH_BfL6lu1KBefEGtBgVrzZAO6t761DZJdiTJOwS7BMOWG8Zl0ld5JTOMkKLxvNXkOHQF1HEmj81OT2uCIQXw`; synchronized 2026-09-13
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — quality and delivery gates; revision `ANLCKQkkB1G56aSiQB7L23wVNmpvzhQIZe0cPHfvg2OExx002hR34HnvYPBHmJxA35VH9qofb5e5t464P2K8YQLsSrKIJVeGFUTvo3wRJw`; synchronized 2026-09-13
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — modular-monolith and source-of-truth boundaries; synchronized 2026-09-13
- [SLO/SLA/Error-Budget Specification](https://docs.google.com/document/d/1lsprPtWWUUyE-bywPz8y-yfclh0BHVBipEAbn3RVji4/edit) — measurement context; synchronized 2026-09-13
- [Environment Configuration Matrix](https://docs.google.com/document/d/1NMBlajs0dj0TD_TbrslKSQbpfxU9sN4zT3GJwz0Vdn4/edit) — environment separation; synchronized 2026-09-13
- Owner-approved S1-L02 contract in this task dated 2026-09-13
- [ADR-047](../../adr/ADR-047-operational-dashboard.md) — canonical implementation decision

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6001 | L02 staging telemetry topology | OTLP/HTTP adapter, API/Worker bootstrap config, pinned SDK/exporter | TC-6001, TC-6002 |
| REQ-6002 | Fail-open/bounded telemetry | bounded dispatcher, non-blocking enqueue, bounded exporter/shutdown, no-op fallback | TC-6003, TC-6004 |
| REQ-6003 | D2 API health | route-template request counter and duration histogram; D2 JSON | TC-6005, TC-6006 |
| REQ-6004 | D3 async health | Worker/Outbox metrics, PostgreSQL Job/Outbox views, D3 JSON | TC-6007, TC-6008 |
| REQ-6005 | D4 AI operations | Usage Ledger metrics, validation metrics, private cost summary, D4 JSON | TC-6009, TC-6010 |
| REQ-6006 | Canonical DB queue/outbox state | atomic snapshot views and partial supporting indexes | TC-6011, TC-6012 |
| REQ-6007 | Least-privilege observer | `aria_observer`, curated view grants, no base/Data API grants | TC-6013, TC-6014 |
| REQ-6008 | Cardinality/content safety | per-instrument allowlists, normalized model allowlist, identifier/content rejection | TC-6015, TC-6016 |
| REQ-6009 | Dashboard-as-Code | three stable UID/version JSON dashboards and import instructions | TC-6017, TC-6018 |

## Assumptions and Clarifications

- Direct OTLP is enabled only when the complete explicit environment setting group is present and
  is rejected in Production; no timeout, interval, capacity or model vocabulary default was added.
- PostgreSQL `jobs.status='queued'` and Outbox `published_at IS NULL` implement the owner-approved
  canonical definitions. Redis remains transport-only.
- Project cost is exposed only through the private aggregate view; it is deliberately absent from
  metric dimensions.
- The migration creates the observer role without a password. Credential provisioning and rotation
  stay outside source control and deployment automation in this increment.

**Unapproved assumptions:** None

## Changes

- Added provider-neutral operational metrics contracts, strict attribute policy, a bounded
  dispatcher, no-op fallback and the Infrastructure-only OpenTelemetry OTLP/HTTP adapter.
- Instrumented API route-template outcomes, Worker execution, Outbox publishing, authoritative
  Usage Ledger commits, and AI schema/business validation failures.
- Added migration `0019` with `observability` views, least-privilege role/grants, and focused partial
  indexes for queued Job and unpublished Outbox age queries.
- Added stable D2/D3/D4 Grafana dashboard JSON and import guidance.
- Added Python, PostgreSQL integration and Node contract/leakage/dashboard tests; pinned the approved
  OpenTelemetry 1.44.0 dependency family in both runtime lockfiles.

## Structure Preservation

- No deployable service, API endpoint, Domain entity, Provider adapter or queue behavior changed.
- OpenTelemetry/Grafana types remain inside Observability Infrastructure and composition roots;
  Domain code has no SDK dependency.
- Application instrumentation consumes provider-neutral metrics contracts and remains optional.
- PostgreSQL remains the Job/Outbox/Usage source of truth; Redis is not promoted to canonical state.
- Existing tenant, modular-monolith, Web RTL/design-system and public API structures are unchanged.

## Senior Review

**Status:** PASS.

Review verified exporter failure isolation, bounded queues, exact per-instrument status/attribute
allowlists, raw-path rejection, normalized model labels, Job/Outbox snapshot semantics, role
privileges, view exposure, migration downgrade/recovery, dashboard query/UID stability and absence
of new alert policy. During review, Worker completion failure was brought inside the failed-job
measurement boundary, Critical Rule evaluation failures were added to business-validation metrics,
and status validation was tightened from a shared union to an instrument-specific vocabulary.

## Verification

Focused contract, unit and real PostgreSQL migration tests pass. Full repository lint, strict type
checking, Web/API/Worker tests, builds, architecture validation, development-record validation,
secret scan and whitespace check pass; evidence is recorded in [test-report.md](./test-report.md).

## Remaining Risks

- Hosted Grafana datasource creation/import and live Staging telemetry evidence require credentials
  and are operational follow-up, not committed secrets.
- Real provider metrics remain dormant until G02/G03 selects and integrates approved providers and
  normalized model identifiers.
- Production Collector/Alloy topology and alert thresholds/durations remain explicitly deferred.
