import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("AI-05 freezes durable identity, exact revisions, and the DB active-job guard", async () => {
  const scheduler = await read("apps/api/app/modules/scope/application/generation_jobs.py");
  const migration = await read("apps/api/migrations/versions/0029_scope_generation_runtime.py");
  assert.match(scheduler, /SCOPE_GENERATION_JOB_TYPE = "scope_generation"/);
  assert.match(scheduler, /SCOPE_GENERATION_EVENT_TYPE = "scope\.generation_requested\.v1"/);
  assert.match(scheduler, /context_item_revisions/);
  assert.match(scheduler, /requirement_revisions/);
  assert.match(scheduler, /gap_revisions/);
  assert.match(migration, /uq_jobs_active_scope_generation_revision/);
  assert.match(migration, /status IN \('queued','running'\)/);
});

test("AI-05 queue message is identifier-only with no automatic retry", async () => {
  const task = await read("apps/worker/app/infrastructure/queue/scope_generation_task.py");
  const consumer = await read("apps/worker/app/application/scope_generation_consumer.py");
  const publisher = await read("apps/worker/app/infrastructure/queue/outbox_publisher.py");
  assert.match(task, /SCOPE_GENERATION_TASK_NAME = "aria\.scope\.generate\.v1"/);
  assert.match(task, /autoretry_for=\(\)/);
  assert.match(publisher, /scope\.generation_requested\.v1/);
  for (const field of ["message_version", "outbox_event_id", "job_id"]) {
    assert.match(consumer, new RegExp(field));
  }
  for (const value of [task, consumer, publisher]) {
    assert.doesNotMatch(value, /customer_content|prompt_text|raw_text/);
  }
});

test("AI-05 finalizes Draft and Job in one transaction after pin recheck", async () => {
  const adapter = await read("apps/worker/app/infrastructure/db/scope_generation_runtime.py");
  const recheck = adapter.indexOf("_pins_match(", adapter.indexOf("async def finalize("));
  const insert = adapter.indexOf("INSERT INTO public.scope_drafts", recheck);
  const success = adapter.indexOf("UPDATE public.jobs SET status='succeeded'", insert);
  const commit = adapter.indexOf("await self._commit(transaction)", success);
  assert.ok(recheck >= 0 && recheck < insert && insert < success && success < commit);
  assert.match(adapter, /SCOPE_GENERATION_INPUT_CHANGED|ScopeGenerationInputChangedError/);
  assert.match(adapter, /lock_scope_generation_inputs/);
  assert.match(adapter, /await transaction\.rollback\(\)/);
});

test("AI-05 is internal and synthetic-only, absent from hosted composition", async () => {
  const apiMain = await read("apps/api/app/main.py");
  const workerMain = await read("apps/worker/app/main.py");
  const fake = await read("apps/worker/app/infrastructure/ai/synthetic_scope_generation.py");
  const adr = await read("docs/adr/ADR-062-scope-generation-runtime-foundation.md");
  assert.doesNotMatch(apiMain, /ScheduleScopeGenerationUseCase/);
  assert.doesNotMatch(workerMain, /register_scope_generation_task|SyntheticScopeGenerationAI/);
  assert.match(fake, /provider = "synthetic"/);
  assert.match(fake, /input_tokens=0/);
  assert.match(adr, /\*\*Status:\*\* Accepted/);
  assert.match(adr, /SCOPE_GENERATION_INPUT_CHANGED/);
});
