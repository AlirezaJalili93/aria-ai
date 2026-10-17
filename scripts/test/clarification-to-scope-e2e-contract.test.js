import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0082 freezes two upfront questions and unchanged ADR-038 resolution", async () => {
  const adr = await read(
    "docs/adr/ADR-068-controlled-clarification-to-scope-e2e.md",
  );
  const harness = await read("tests/e2e/controlled_context_to_scope_api.py");
  const repository = await read(
    "apps/api/app/modules/gaps/infrastructure/clarification_repository.py",
  );

  assert.match(adr, /Status:\*\* Accepted \/ Frozen/);
  assert.match(adr, /Both\s+questions must exist before either answer is recorded/);
  assert.match(adr, /answer Question 1 while the Gap stays open/);
  assert.match(harness, /CreateClarificationQuestionCommand/);
  assert.match(harness, /ResolveClarificationCommand/);
  assert.match(harness, /\["answered", "open"\]/);
  assert.match(harness, /Gap resolved before all upfront questions were answered/);
  assert.match(repository, /index_where=text\("status = 'open'"\)/);
  assert.doesNotMatch(harness, /UPDATE\s+(?:public\.)?(?:gaps|clarifications)/i);
});

test("0082 preserves explicit Scope gating and the J03-B boundary", async () => {
  const adr = await read(
    "docs/adr/ADR-068-controlled-clarification-to-scope-e2e.md",
  );
  const harness = await read("tests/e2e/controlled_context_to_scope_api.py");
  const scopeRuntime = await read(
    "apps/worker/app/infrastructure/db/scope_generation_runtime.py",
  );

  assert.match(adr, /Incorporating answer meaning into Context\/Requirements remains J03-B/);
  assert.match(harness, /semantic_state_snapshot/);
  assert.match(harness, /Mid-clarification AI-05 created a side effect/);
  assert.match(harness, /Clarification text leaked into AI-05 Job input/);
  assert.match(harness, /CONTROLLED_0082_E2E=PASS/);
  assert.doesNotMatch(scopeRuntime, /clarification_resolutions|answer_text/);
});

test("0082 runner includes PostgreSQL replay, isolation, pinning and rollback gates", async () => {
  const runner = await read("tests/e2e/run-clarification-to-scope-controlled.ps1");
  assert.match(runner, /--clarification-resolution/);
  assert.match(runner, /test_clarification_postgres\.py/);
  assert.match(runner, /test_synthetic_runtime_tenant_isolation_postgres\.py/);
  assert.match(runner, /test_scope_generation_runtime_postgres\.py/);
  assert.match(runner, /CONTROLLED_0082_GATE=PASS/);
});
