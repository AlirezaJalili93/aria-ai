import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("AI-01 scheduling uses the frozen durable identities and DB active-job guard", async () => {
  const scheduler = await read(
    "apps/api/app/modules/context/application/context_structuring_jobs.py",
  );
  const migration = await read(
    "apps/api/migrations/versions/0026_context_structuring_runtime.py",
  );

  assert.match(scheduler, /CONTEXT_STRUCTURING_JOB_TYPE = "context_structuring"/);
  assert.match(
    scheduler,
    /CONTEXT_STRUCTURING_EVENT_TYPE = "context\.structuring_requested\.v1"/,
  );
  assert.match(scheduler, /CONTEXT_STRUCTURING_ROUTE_KEY = "POST \/api\/v1\/projects\/\{project_id\}\/context-structuring"/);
  assert.match(scheduler, /unit_of_work\.idempotency\.reserve/);
  assert.match(scheduler, /unit_of_work\.idempotency\.complete/);
  assert.match(migration, /uq_jobs_active_context_structuring_project/);
  assert.match(migration, /status IN \('queued','running'\)/);
});

test("Queue delivery contains identifiers only and has no automatic retry", async () => {
  const publisher = await read("apps/worker/app/infrastructure/queue/outbox_publisher.py");
  const task = await read("apps/worker/app/infrastructure/queue/context_structuring_task.py");
  const consumer = await read("apps/worker/app/application/context_structuring_consumer.py");

  assert.match(publisher, /aria\.context\.structure\.v1/);
  assert.match(publisher, /message_version/);
  assert.match(publisher, /outbox_event_id/);
  assert.match(publisher, /job_id/);
  assert.match(task, /autoretry_for=\(\)/);
  assert.match(consumer, /set\(payload\) != \{/);
  for (const value of [publisher, task, consumer]) {
    assert.doesNotMatch(value, /customer_content|prompt_text|raw_text/);
  }
});

test("Context, Project version and Job success share one transaction boundary", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/context_structuring.py",
  );
  const repository = await read(
    "apps/worker/app/infrastructure/db/context_structuring_runtime.py",
  );

  const add = application.indexOf("await unit_of_work.repository.add_batch");
  const advance = application.indexOf("await unit_of_work.repository.advance_project_version");
  const complete = application.indexOf("await unit_of_work.repository.complete_job_success");
  const commit = application.indexOf("await unit_of_work.commit()");
  assert.ok(add >= 0 && add < advance && advance < complete && complete < commit);
  assert.match(repository, /status='succeeded'/);
  assert.match(repository, /status='running'/);
  assert.match(repository, /await self\._transaction\.rollback\(\)/);
});

test("0071 remains synthetic-only and is not activated publicly or in hosted runtime", async () => {
  const apiMain = await read("apps/api/app/main.py");
  const workerMain = await read("apps/worker/app/main.py");
  const fake = await read(
    "apps/worker/app/infrastructure/ai/synthetic_context_structuring.py",
  );
  const adr = await read(
    "docs/adr/ADR-058-context-structuring-job-runtime-foundation.md",
  );

  assert.doesNotMatch(apiMain, /create_context_structuring_router|ScheduleContextStructuringUseCase/);
  assert.doesNotMatch(workerMain, /SyntheticContextStructuringAI|aria\.context\.structure\.v1/);
  assert.match(fake, /provider = "synthetic"/);
  assert.match(fake, /input_tokens=0/);
  assert.match(adr, /Public Endpoint.*Disabled/is);
  assert.match(adr, /Hosted activation.*disabled/is);
  assert.match(adr, /Customer content.*prohibited/is);
});

test("Worker authority is limited to the required Project column and AI Context inserts", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0026_context_structuring_runtime.py",
  );

  assert.match(migration, /GRANT SELECT ON TABLE public\.projects TO aria_worker/);
  assert.match(migration, /GRANT UPDATE \(current_context_version\)/);
  assert.doesNotMatch(migration, /GRANT SELECT, UPDATE ON TABLE public\.projects/);
  assert.match(migration, /GRANT INSERT ON TABLE public\.context_items TO aria_worker/);
  assert.match(migration, /created_by_type = 'ai' AND created_by IS NULL/);
});
