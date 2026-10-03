# ADR-047 — Operational Dashboard Baseline

- **Status:** Accepted — owner approval received 2026-09-13
- **Story:** S1-L02 — Operational Dashboard
- **Supersedes:** No prior accepted operational dashboard implementation

## Decision

Staging API and Worker may export operational metrics directly through OpenTelemetry OTLP/HTTP to
Grafana Cloud. OpenTelemetry SDK/exporter types are restricted to the Observability infrastructure
package and application bootstrap. Domain code remains unaware of OpenTelemetry and Grafana.
Production collector/Alloy topology is deferred and direct OTLP configuration is rejected when
`APP_ENV=production`.

Telemetry is fail-open: instrumentation uses a bounded, non-blocking in-process queue, bounded
export interval/timeout, drops unknown or saturated records, and cannot fail an API request, Worker
job, Outbox publish or Usage Ledger commit. Model labels must be normalized members of a deployment
allowlist. Per-instrument attribute allowlists reject unknown attributes, raw paths, UUIDs and all
customer/content-bearing values.

## Dashboard and source-of-truth decisions

The source-controlled dashboards have stable UIDs and version metadata:

- D2 API Health: request count, 5xx rate, p50/p95/p99 latency by route template.
- D3 Async Health: PostgreSQL queued count/age, Worker outcomes/duration, PostgreSQL Outbox
  count/age and Outbox publish failures.
- D4 AI Operations: provider outcomes/latency, schema/business validation failures and Usage Ledger
  cost by day/task/project.

Canonical `queue_depth` is `count(jobs where status='queued')`; queued age uses the oldest such
`created_at`. Both values come from one PostgreSQL view snapshot. Canonical Outbox pending state is
`published_at IS NULL`. Redis message count is not business queue depth. AI cost-by-project is
aggregated from a private PostgreSQL view and `project_id` is never a metric label.

## Database security

`aria_observer` is `LOGIN NOINHERIT NOBYPASSRLS` and receives `USAGE` on `observability` plus
`SELECT` only on the four approved security-barrier views: `job_health`,
`job_execution_health`, `outbox_health` and `ai_cost_summary`. It receives no base-table grants.
`anon` and `authenticated` receive no schema or view access. The role password and Grafana
datasource credential are provisioned out of band and are never committed or logged.

The views intentionally run under their owner and expose only bounded operational projections;
this permits the observer role to avoid broad base-table access while retaining a narrow dashboard
surface. No new alert is introduced because alert thresholds/durations are not frozen for L02.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L02; synchronized 2026-09-13.
- [Observability & Incident Response Runbook](https://docs.google.com/document/d/1oze9K7tyvmAEOYK5Ddt1LyzOcGPe_7Ru28JE23g2xPE/edit) — D2/D3/D4 and cardinality baseline; synchronized 2026-09-13.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — execution and quality gates; synchronized 2026-09-13.
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — modular-monolith boundaries; synchronized 2026-09-13.
- [SLO/SLA/Error-Budget Specification](https://docs.google.com/document/d/1lsprPtWWUUyE-bywPz8y-yfclh0BHVBipEAbn3RVji4/edit) — measurement context; synchronized 2026-09-13.
- [Environment Configuration Matrix](https://docs.google.com/document/d/1NMBlajs0dj0TD_TbrslKSQbpfxU9sN4zT3GJwz0Vdn4/edit) — environment boundary; synchronized 2026-09-13.
- Owner-approved S1-L02 contract in this task, 2026-09-13.

