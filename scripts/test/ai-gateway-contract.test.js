import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const gateway = readFileSync(
  resolve(root, "apps/worker/app/application/ai_execution.py"),
  "utf8",
);
const adr = readFileSync(resolve(root, "docs/adr/ADR-021-ai-execution-port.md"), "utf8");

test("AI gateway boundary uses the canonical provider-neutral signature", () => {
  assert.match(gateway, /class AIExecutionPort\(Protocol\)/);
  for (const parameter of [
    "task_type",
    "workflow_version",
    "prompt_version",
    "output_schema",
    "input_context",
    "routing_policy",
    "cost_budget",
    "timeout_policy",
    "metadata",
  ]) {
    assert.match(gateway, new RegExp(parameter));
  }
  for (const field of [
    "data",
    "provider",
    "model",
    "provider_request_id",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "latency_ms",
    "retry_no",
    "workflow_version",
    "prompt_version",
    "estimated_cost",
    "status",
  ]) {
    assert.match(gateway, new RegExp(field));
  }
});

test("AI errors are standardized without coupling Application to a provider SDK", () => {
  assert.match(gateway, /class AIExecutionError\(RuntimeError\)/);
  for (const errorClass of [
    "timeout",
    "rate_limited",
    "auth_error",
    "invalid_response",
    "safety_block",
    "provider_unavailable",
    "quota_error",
    "unknown_provider_error",
  ]) {
    assert.match(gateway, new RegExp(errorClass));
  }
  assert.doesNotMatch(gateway, /openai|anthropic|gemini|google\.generativeai|redis|celery/i);
  assert.match(adr, /timeout.*rate_limited.*auth_error/s);
  assert.match(adr, /Infrastructure adapters/);
});
