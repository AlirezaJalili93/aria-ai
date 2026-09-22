import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

test("0024 stores one idempotent record per actual Provider invocation", () => {
  const migration = read("apps/api/migrations/versions/0024_ai_failure_accounting.py");
  const ledger = read("apps/worker/app/infrastructure/db/usage_ledger.py");

  assert.match(migration, /provider_attempt_id/);
  assert.match(migration, /uq_usage_records_provider_attempt_id/);
  assert.match(migration, /accounting_status IN \('complete','unavailable'\)/);
  assert.match(migration, /input_tokens IS NULL/);
  assert.match(migration, /estimated_cost IS NULL/);
  assert.match(ledger, /on_conflict_do_nothing\(index_elements=\["provider_attempt_id"\]\)/);
});

test("failure policy bounds primary retry and one-shot fallback", () => {
  const policy = read("apps/worker/app/application/provider_failure_policy.py");

  assert.match(policy, /MAX_PRIMARY_ATTEMPTS = 2/);
  assert.match(policy, /MAX_FALLBACK_ATTEMPTS = 1/);
  assert.match(policy, /MAX_TOTAL_PROVIDER_INVOCATIONS = 3/);
  assert.match(policy, /"timeout", "rate_limited", "provider_unavailable"/);
  assert.match(policy, /"timeout", "provider_unavailable"/);
  assert.match(policy, /FallbackAuthorizationPort/);
  assert.match(policy, /quality_allowed and self\.budget_allowed/);
  assert.doesNotMatch(policy, /OpenAI|Gemini|gpt-|gemini-/i);
});

test("0069 documents real-provider promotion and customer content as deferred", () => {
  const adr = read("docs/adr/ADR-056-ai-failure-policy.md");

  assert.match(adr, /Primary candidate:\s*none/i);
  assert.match(adr, /Fallback candidate:\s*none/i);
  assert.match(adr, /synthetic/i);
  assert.match(adr, /customer content.*prohibited/is);
});
