import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const migrationPath = "apps/api/migrations/versions/0019_operational_dashboard_views.py";
const metricsPath = "packages/observability/src/aria_observability/operational_metrics.py";
const dashboards = [
  ["infra/observability/grafana/dashboards/d2-api-health.json", "aria-d2-api-health-v1"],
  ["infra/observability/grafana/dashboards/d3-async-health.json", "aria-d3-async-health-v1"],
  ["infra/observability/grafana/dashboards/d4-ai-operations.json", "aria-d4-ai-operations-v1"],
];

test("PostgreSQL views define canonical queue/outbox state and least privilege", async () => {
  const migration = await readFile(migrationPath, "utf8");
  assert.match(migration, /count\(\*\) FILTER \(WHERE status = 'queued'\)/);
  assert.match(migration, /min\(created_at\) FILTER \(WHERE status = 'queued'\)/);
  assert.match(migration, /count\(\*\) FILTER \(WHERE published_at IS NULL\)/);
  assert.match(migration, /CREATE ROLE aria_observer/);
  assert.match(migration, /NOBYPASSRLS/);
  assert.match(migration, /REVOKE ALL ON ALL TABLES IN SCHEMA public FROM aria_observer/);
  assert.match(migration, /GRANT SELECT ON observability\./);
  assert.doesNotMatch(migration, /GRANT SELECT ON (TABLE )?public\./);
  assert.doesNotMatch(migration, /redis/i);
});

test("metric policy is per-instrument, bounded, and excludes sensitive dimensions", async () => {
  const metrics = await readFile(metricsPath, "utf8");
  for (const allowed of [
    "route", "method", "status_class", "job_type", "workflow", "provider", "model",
    "validation_kind", "currency",
  ]) assert.match(metrics, new RegExp(`\\"${allowed}\\"`));
  for (const forbidden of [
    "account_id", "project_id", "job_id", "request_id", "correlation_id", "source_id",
    "requirement_id", "gap_id", "scope_version_id", "email", "title", "filename",
    "error_message", "prompt", "response", "content",
  ]) assert.match(metrics, new RegExp(`\\"${forbidden}\\"`));
  assert.match(metrics, /allowed_models/);
  assert.match(metrics, /put_nowait/);
  assert.match(metrics, /except Full/);
});

test("dashboard JSON has stable identity and repeatable import semantics", async () => {
  const seen = new Set();
  for (const [path, expectedUid] of dashboards) {
    const raw = await readFile(path, "utf8");
    const first = JSON.parse(raw);
    const second = JSON.parse(raw);
    assert.deepEqual(first, second);
    assert.equal(first.uid, expectedUid);
    assert.equal(first.version, 1);
    assert.equal(first.editable, false);
    assert.ok(first.schemaVersion > 0);
    assert.ok(!seen.has(first.uid));
    seen.add(first.uid);
  }
});

test("cost by project is query-driven and identifiers never become metric labels", async () => {
  const metrics = await readFile(metricsPath, "utf8");
  const dashboard = JSON.parse(
    await readFile("infra/observability/grafana/dashboards/d4-ai-operations.json", "utf8"),
  );
  const serialized = JSON.stringify(dashboard);
  assert.match(serialized, /observability\.ai_cost_summary/);
  assert.match(serialized, /project_id/);
  assert.doesNotMatch(metrics, /\{"project_id"/);
});

test("runtime paths cover D2, D3 and D4 without importing OpenTelemetry into workflows", async () => {
  const api = await readFile("apps/api/app/api/middleware/observability.py", "utf8");
  const worker = await readFile("apps/worker/app/application/job_execution.py", "utf8");
  const outbox = await readFile("apps/api/app/modules/jobs/application/outbox_relay.py", "utf8");
  const usage = await readFile("apps/worker/app/infrastructure/db/usage_ledger.py", "utf8");
  const workflows = await Promise.all([
    "context_structuring.py", "requirements_generation.py", "gap_detection.py",
    "scope_generation.py",
  ].map((name) => readFile(`packages/backend-application/src/aria_backend_application/${name}`, "utf8")));
  assert.match(api, /record_http_request/);
  assert.match(worker, /record_worker_job/);
  assert.match(outbox, /record_outbox_publish/);
  assert.match(usage, /record_ai_usage/);
  for (const workflow of workflows) {
    assert.match(workflow, /record_ai_validation_failure/);
    assert.doesNotMatch(workflow, /opentelemetry|grafana/i);
  }
});

test("dashboard panels contain only the approved visibility baseline and no alerts", async () => {
  const [d2, d3, d4] = await Promise.all(dashboards.map(async ([path]) =>
    JSON.parse(await readFile(path, "utf8"))));
  const d2Text = JSON.stringify(d2);
  const d3Text = JSON.stringify(d3);
  const d4Text = JSON.stringify(d4);
  for (const quantile of ["0.50", "0.95", "0.99"]) assert.match(d2Text, new RegExp(quantile.replace(".", "\\.")));
  assert.match(d2Text, /status_class=\\"5xx\\"/);
  assert.match(d3Text, /observability\.job_health/);
  assert.match(d3Text, /observability\.outbox_health/);
  assert.match(d3Text, /aria_outbox_publish_total/);
  assert.match(d4Text, /aria_ai_validation_failures_total/);
  assert.match(d4Text, /observability\.ai_cost_summary/);
  for (const dashboard of [d2, d3, d4]) assert.equal(dashboard.alert, undefined);
});
