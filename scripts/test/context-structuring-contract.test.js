import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const workflow = readFileSync(
  resolve(root, "packages/backend-application/src/aria_backend_application/context_structuring.py"),
  "utf8",
);
const worker = readFileSync(
  resolve(root, "apps/worker/app/application/context_structuring.py"),
  "utf8",
);
const adr = readFileSync(
  resolve(root, "docs/adr/ADR-026-context-structuring-workflow.md"),
  "utf8",
);

test("H02 remains provider neutral and validate-first", () => {
  for (const symbol of [
    "ContextStructuringUseCase",
    "resolve_latest_ready",
    "AIExecutionPort",
    "UnsupportedClaimValidator",
    "allocate_next_version",
    "add_batch",
    "advance_project_version",
    "DUPLICATE_CONTEXT_ITEM",
  ]) {
    assert.match(workflow, new RegExp(symbol));
  }
  assert.doesNotMatch(workflow, /openai|anthropic|gemini|google\.genai|celery|redis/i);
  assert.match(adr, /exact.*item_type.*content.*reject/s);
});

test("Worker delegates to the shared use case without owning Context rules", () => {
  assert.match(worker, /aria_backend_application\.context_structuring/);
  assert.match(worker, /await self\._use_case\.execute\(command\)/);
  assert.doesNotMatch(worker, /source_refs|DUPLICATE_CONTEXT_ITEM|canonical_text/);
});

test("H02 exclusions remain explicit", () => {
  for (const exclusion of [
    "Public endpoint",
    "concrete Job type",
    "Queue transport",
    "Repair",
    "Provider adapter",
    "entitlement",
    "quota",
  ]) {
    assert.match(adr, new RegExp(exclusion, "i"));
  }
});
