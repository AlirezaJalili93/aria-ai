# Grafana operational dashboards

These source-controlled dashboards implement the approved S1-L02 staging baseline. Import the
JSON files with the Prometheus-compatible Grafana Cloud metrics datasource and the PostgreSQL
datasource whose credential maps to `aria_observer`.

- `d2-api-health.json`: request volume, 5xx rate, and p50/p95/p99 HTTP latency.
- `d3-async-health.json`: durable PostgreSQL queue/outbox state plus Worker outcomes.
- `d4-ai-operations.json`: provider outcomes/latency, validation failures, and Usage Ledger cost.

The UIDs are stable, so importing the same file updates the existing dashboard. Direct OTLP/HTTP
is approved only for staging. Production collector/Alloy topology and all new alerts are deferred.
The PostgreSQL datasource must use `aria_observer`; it must not use an API or Worker credential.

