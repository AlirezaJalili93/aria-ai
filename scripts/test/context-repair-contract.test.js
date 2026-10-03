import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const workflow = readFileSync(
  resolve(root, "packages/backend-application/src/aria_backend_application/context_structuring.py"),
  "utf8",
);
const usage = readFileSync(
  resolve(root, "packages/backend-application/src/aria_backend_application/usage_ledger.py"),
  "utf8",
);
const migration = readFileSync(
  resolve(root, "apps/api/migrations/versions/0009_usage_repair_number.py"),
  "utf8",
);
const adapter = readFileSync(
  resolve(root, "apps/worker/app/infrastructure/db/usage_ledger.py"),
  "utf8",
);
const adr = readFileSync(
  resolve(root, "docs/adr/ADR-027-context-validation-repair.md"),
  "utf8",
);

test("H03 exposes a bounded, versioned, provider-neutral repair policy", () => {
  for (const symbol of [
    "ContextRepairPolicy",
    "max_repairs",
    "repair_prompt_version",
    "CONTEXT_REPAIR_EXHAUSTED",
    "AIExecutionPort",
  ]) {
    assert.match(workflow, new RegExp(symbol));
  }
  assert.doesNotMatch(workflow, /openai|anthropic|gemini|google\.genai/i);
  assert.match(adr, /max_repairs.*1/s);
  assert.match(adr, /max_repairs=0.*original structured validation/s);
});

test("repair number is separate in Application and PostgreSQL contracts", () => {
  assert.match(usage, /repair_no:\s*int/);
  assert.match(migration, /repair_no/);
  assert.match(migration, /SmallInteger/);
  assert.match(migration, /server_default=["']0["']/);
  assert.match(migration, /repair_no >= 0/);
  assert.doesNotMatch(migration, /repair_no <= 1/);
  assert.match(adapter, /repair_no=record\.repair_no/);
});

test("H03 keeps repair data ephemeral and transport decisions deferred", () => {
  assert.match(adr, /ephemeral/i);
  assert.match(adr, /same.*routing/is);
  assert.match(adr, /provider retries.*repair_no/is);
  assert.match(adr, /no Context\s+write/i);
  assert.doesNotMatch(workflow, /fallback_provider|escalation_tier|celery|redis/i);
});
