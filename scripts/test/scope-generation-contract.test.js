import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const application = "packages/backend-application/src/aria_backend_application/scope_generation.py";
const adr = "docs/adr/ADR-043-scope-generation-use-case.md";

test("K03 is provider-neutral and uses the approved K01 contract", async () => {
  const source = await readFile(application, "utf8");
  assert.match(source, /AIExecutionPort/);
  assert.match(source, /UsageLedger/);
  assert.match(source, /scope_content_schema_v1/);
  assert.match(source, /ScopeGenerationRequirement/);
  assert.match(source, /\{"draft", "confirmed"\}/);
  assert.doesNotMatch(source, /openai|anthropic|gemini|sqlalchemy|fastapi|celery|redis/i);
});

test("K03 maps AI-05 into twelve K01 sections without an implicit thirteenth section", async () => {
  const source = await readFile(adr, "utf8");
  for (const section of [
    "summary",
    "goals",
    "pages_sections",
    "requirements",
    "content",
    "visual_direction",
    "constraints",
    "assumptions",
    "resolved_gaps",
    "remaining_non_blocking_gaps",
    "out_of_scope",
    "acceptance_notes",
  ]) assert.match(source, new RegExp(`\\b${section}\\b`));
  assert.match(source, /Pages.*Sections|Pages \+ Sections/);
  assert.match(source, /structural/i);
  assert.doesNotMatch(source, /thirteenth section.*create/i);
});

test("K03 refuses an existing Draft before AI, never overwrites, and meters every invocation", async () => {
  const source = await readFile(application, "utf8");
  const adrSource = await readFile(adr, "utf8");
  assert.match(source, /SCOPE_DRAFT_ALREADY_EXISTS/);
  assert.match(source, /draft_writer\.exists/);
  assert.match(source, /_execute_with_repair/);
  assert.match(source, /usage_ledger\.append/);
  assert.match(adrSource, /no implicit overwrite|never silently overwrites/i);
  assert.match(adrSource, /regeneration.*separate/i);
});

test("K03 logging contract excludes generated content and raw provider material", async () => {
  const source = await readFile(adr, "utf8");
  assert.match(source, /scope\.generation_started/);
  assert.match(source, /scope\.generation_completed/);
  assert.match(source, /scope\.generation_failed/);
  assert.match(source, /raw provider response/i);
  assert.match(source, /without.*content|never.*content/i);
});
