import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const metrics = readFileSync(
  resolve(root, "apps/worker/app/application/parser_metrics.py"),
  "utf8",
);
const parser = readFileSync(
  resolve(root, "apps/worker/app/application/context_parser.py"),
  "utf8",
);
const adr = readFileSync(resolve(root, "docs/adr/ADR-020-parser-metrics.md"), "utf8");

test("parser metrics stay provider-neutral and expose only approved measurements", () => {
  assert.match(metrics, /class ParserMetrics\(Protocol\)/);
  for (const term of ["observe_parse_latency", "observe_queue_wait", "record_parse_outcome"]) {
    assert.match(metrics, new RegExp(term));
  }
  for (const label of ["unsupported_format", "empty", "parse_error", "timeout"]) {
    assert.match(metrics, new RegExp(label));
  }
  assert.doesNotMatch(metrics, /prometheus|opentelemetry|redis|celery/i);
});

test("parser instrumentation does not place identifiers or free text in metric labels", () => {
  assert.match(parser, /parser_type="text"/);
  assert.match(parser, /source_id=str\(source_version\.id\)/);
  assert.doesNotMatch(parser, /observe_parse_latency\([^)]*source_id/i);
  assert.match(adr, /Tenant, Project, Source, Job/);
  assert.match(adr, /failure_rate/);
});
