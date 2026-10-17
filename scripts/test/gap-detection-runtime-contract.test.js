import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("AI-03 uses frozen durable identities and exact dual revision binding", async () => {
  const scheduler = await read("apps/api/app/modules/gaps/application/detection_jobs.py");
  const migration = await read("apps/api/migrations/versions/0028_gap_detection_runtime.py");
  assert.match(scheduler, /GAP_DETECTION_JOB_TYPE = "gap_detection"/);
  assert.match(scheduler, /GAP_DETECTION_EVENT_TYPE = "gap\.detection_requested\.v1"/);
  assert.match(scheduler, /context_item_revisions/);
  assert.match(scheduler, /requirement_revisions/);
  assert.match(scheduler, /completion_checklist_version/);
  assert.match(scheduler, /critical_rule_pack_version/);
  assert.match(migration, /uq_jobs_active_gap_detection_revision/);
});

test("AI-03 transport is identifier-only and has no automatic retry", async () => {
  const publisher = await read("apps/worker/app/infrastructure/queue/outbox_publisher.py");
  const task = await read("apps/worker/app/infrastructure/queue/gap_detection_task.py");
  const consumer = await read("apps/worker/app/application/gap_detection_consumer.py");
  assert.match(publisher, /aria\.gaps\.detect\.v1/);
  assert.match(task, /autoretry_for=\(\)/);
  assert.match(consumer, /message_version/);
  assert.match(consumer, /outbox_event_id/);
  assert.match(consumer, /job_id/);
  for (const value of [publisher, task, consumer]) {
    assert.doesNotMatch(value, /customer_content|prompt_text|raw_text/);
  }
});

test("Gap writes, deterministic rule result and Job success share one transaction", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );
  const repository = await read("apps/worker/app/infrastructure/db/gap_detection_runtime.py");
  const add = application.indexOf("await repository.add_batch");
  const complete = application.indexOf("await repository.mark_job_succeeded");
  const commit = application.indexOf("await unit_of_work.commit()", complete);
  assert.ok(add >= 0 && add < complete && complete < commit);
  assert.match(repository, /status='succeeded'/);
  assert.match(repository, /status='running'/);
  assert.match(repository, /await self\._transaction\.rollback\(\)/);
});

test("Empty Requirements remain valid while usable Context is mandatory", async () => {
  const scheduler = await read("apps/api/app/modules/gaps/application/detection_jobs.py");
  const store = await read("apps/worker/app/infrastructure/db/gap_detection_runtime.py");
  const fake = await read("apps/worker/app/infrastructure/ai/synthetic_gap_detection.py");
  const requirementParser = store.slice(
    store.indexOf("def _requirement_revisions"),
    store.indexOf("def _context_item"),
  );
  assert.match(scheduler, /if snapshot is None or not snapshot\.context_items/);
  assert.doesNotMatch(scheduler, /not snapshot\.requirements|REQUIREMENTS_REQUIRED/);
  assert.match(requirementParser, /if not isinstance\(value, list\):/);
  assert.doesNotMatch(requirementParser, /(?:or|and) not value|if not value:/);
  assert.match(fake, /requirements = input_context\.get\("requirements"\)/);
  assert.match(fake, /CandidateGapBatch\(\s*items=\(\)/s);
});

test("0074 stays internal, synthetic-only and absent from hosted composition", async () => {
  const apiMain = await read("apps/api/app/main.py");
  const workerMain = await read("apps/worker/app/main.py");
  const fake = await read("apps/worker/app/infrastructure/ai/synthetic_gap_detection.py");
  const adr = await read("docs/adr/ADR-061-gap-detection-runtime-foundation.md");
  assert.doesNotMatch(apiMain, /ScheduleGapDetectionUseCase/);
  assert.doesNotMatch(workerMain, /register_gap_detection_task|SyntheticGapDetectionAI/);
  assert.match(fake, /provider = "synthetic"/);
  assert.match(fake, /input_tokens=0/);
  assert.match(adr, /no public\s+HTTP endpoint/is);
  assert.match(adr, /no AI-02-to-AI-03 chaining/is);
  assert.match(adr, /Customer content.*prohibited/is);
  for (const value of [apiMain, workerMain, fake]) {
    assert.doesNotMatch(value, /OPENAI_API_KEY|GEMINI_API_KEY/);
  }
});

test("Worker Gap authority is insert-only and tenant linkage remains DB-enforced", async () => {
  const migration = await read("apps/api/migrations/versions/0028_gap_detection_runtime.py");
  assert.match(migration, /GRANT SELECT ON TABLE public\.gaps TO aria_worker/);
  assert.match(migration, /GRANT INSERT \(id, account_id, project_id, context_version/);
  assert.match(migration, /GRANT INSERT \(account_id, project_id, gap_id, requirement_id\)/);
  assert.doesNotMatch(migration, /GRANT UPDATE .*public\.gaps/);
  assert.doesNotMatch(migration, /GRANT DELETE/);
});
