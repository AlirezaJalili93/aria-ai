import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync("apps/worker/app/application/routing_policy.py", "utf8");
const adr = fs.readFileSync("docs/adr/ADR-023-limited-routing-policy-contract.md", "utf8");

test("routing policy contract exposes only canonical provider-neutral tiers", () => {
  assert.match(source, /RoutingTier = Literal\["cheap", "standard", "premium"\]/);
  assert.match(source, /class RoutingDecision/);
  assert.match(source, /def resolve\(self, task_type: str, context: StructuredMapping\)/);
  assert.match(source, /routing_policy_required/);
});

test("routing policy contract does not invent provider or task policy", () => {
  assert.doesNotMatch(source, /openai|anthropic|gemini|google\.generativeai|provider_name|model_name/i);
  assert.match(adr, /No task-type vocabulary or task-to-tier mapping is introduced/);
  assert.match(adr, /No default tier is introduced/);
  assert.match(adr, /No automatic premium escalation/);
  assert.match(adr, /No fallback behavior or provider selection is introduced/);
  assert.match(adr, /G02\/G03/);
  assert.match(adr, /Unapproved assumptions:\*\* None/);
});
