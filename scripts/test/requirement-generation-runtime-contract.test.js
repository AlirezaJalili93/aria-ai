import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("AI-02 uses frozen durable identities and exact snapshot binding", async () => {
  const scheduler = await read(
    "apps/api/app/modules/requirements/application/generation_jobs.py",
  );
  const migration = await read(
    "apps/api/migrations/versions/0027_requirement_generation_runtime.py",
  );
  assert.match(scheduler, /REQUIREMENT_GENERATION_JOB_TYPE = "requirement_generation"/);
  assert.match(
    scheduler,
    /REQUIREMENT_GENERATION_EVENT_TYPE = "requirement\.generation_requested\.v1"/,
  );
  assert.match(scheduler, /context_item_revisions/);
  assert.match(scheduler, /snapshot\.revision_vector/);
  assert.match(migration, /uq_jobs_active_requirement_generation_revision/);
});

test("AI-02 transport is identifier-only and has no automatic retry", async () => {
  const publisher = await read("apps/worker/app/infrastructure/queue/outbox_publisher.py");
  const task = await read(
    "apps/worker/app/infrastructure/queue/requirement_generation_task.py",
  );
  const consumer = await read(
    "apps/worker/app/application/requirement_generation_consumer.py",
  );
  assert.match(publisher, /aria\.requirements\.generate\.v1/);
  assert.match(task, /autoretry_for=\(\)/);
  assert.match(consumer, /message_version/);
  assert.match(consumer, /outbox_event_id/);
  assert.match(consumer, /job_id/);
  for (const value of [publisher, task, consumer]) {
    assert.doesNotMatch(value, /customer_content|prompt_text|raw_text/);
  }
});

test("Requirement persistence and Job success share one transaction", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/requirements_generation.py",
  );
  const repository = await read(
    "apps/worker/app/infrastructure/db/requirement_generation_runtime.py",
  );
  const add = application.indexOf("await repository.add_batch");
  const conflicts = application.indexOf("await repository.add_conflict_events");
  const complete = application.indexOf("await repository.complete_job_success");
  const commit = application.indexOf("await unit_of_work.commit()");
  assert.ok(add >= 0 && add < conflicts && conflicts < complete && complete < commit);
  assert.match(repository, /status='succeeded'/);
  assert.match(repository, /status='running'/);
  assert.match(repository, /await self\._transaction\.rollback\(\)/);
});

test("0073 remains internal, synthetic-only and absent from hosted composition", async () => {
  const apiMain = await read("apps/api/app/main.py");
  const workerMain = await read("apps/worker/app/main.py");
  const fake = await read(
    "apps/worker/app/infrastructure/ai/synthetic_requirement_generation.py",
  );
  const adr = await read(
    "docs/adr/ADR-060-requirement-generation-runtime-foundation.md",
  );
  assert.doesNotMatch(apiMain, /ScheduleRequirementGenerationUseCase/);
  assert.doesNotMatch(workerMain, /register_requirement_generation_task|SyntheticRequirementGenerationAI/);
  assert.match(fake, /provider = "synthetic"/);
  assert.match(fake, /input_tokens=0/);
  assert.match(adr, /Explicitly Deferred[\s\S]*Public HTTP trigger/i);
  assert.match(adr, /AI-01.*AI-02 chaining/is);
  assert.match(adr, /customer content.*not approved/is);
  for (const value of [apiMain, workerMain, fake]) {
    assert.doesNotMatch(value, /OPENAI_API_KEY|GEMINI_API_KEY/);
  }
});
