import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const adapter = readFileSync(
  resolve(root, "apps/worker/app/application/provider_adapter.py"),
  "utf8",
);
const adr = readFileSync(resolve(root, "docs/adr/ADR-022-generic-provider-adapter-port.md"), "utf8");
const candidateAdr = readFileSync(
  resolve(root, "docs/adr/ADR-055-provider-adapter-candidates.md"),
  "utf8",
);

test("generic ProviderAdapter exposes only the provider-neutral execute boundary", () => {
  assert.match(adapter, /class ProviderAdapter\(Protocol\)/);
  assert.match(adapter, /async def execute\(self, request: ProviderRequest\) -> ProviderResult/);
  for (const field of [
    "data",
    "provider",
    "model",
    "provider_request_id",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "latency_ms",
    "status",
  ]) {
    assert.match(adapter, new RegExp(field));
  }
  assert.doesNotMatch(adapter, /openai|anthropic|gemini|google\.generativeai|redis|celery/i);
});

test("candidate selection supersedes only the concrete-adapter deferral", () => {
  assert.match(adr, /ADR-055 later selected two evaluation-only/);
  assert.match(adr, /Runtime routing, primary\/fallback promotion.*remain undecided/s);
  assert.match(candidateAdr, /Primary:\s*none/i);
  assert.match(candidateAdr, /Fallback:\s*none/i);
  assert.match(candidateAdr, /Customer content.*prohibited/is);
});
