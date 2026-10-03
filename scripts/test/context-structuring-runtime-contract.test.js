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

test("0072 exposes the command while keeping synthetic and hosted boundaries fail-closed", async () => {
  const apiMain = await read("apps/api/app/main.py");
  const router = await read("apps/api/app/api/routers/context_structuring.py");
  const config = await read("apps/api/app/core/config.py");
  const workerMain = await read("apps/worker/app/main.py");
  const fake = await read(
    "apps/worker/app/infrastructure/ai/synthetic_context_structuring.py",
  );
  const adr = await read(
    "docs/adr/ADR-059-context-structuring-command-synthetic-e2e.md",
  );
  const env = await read(".env.example");
  const railway = await read("infra/railway/README.md");

  assert.match(apiMain, /create_context_structuring_router/);
  assert.match(apiMain, /DenyAllSyntheticContextStructuring/);
  assert.match(router, /await request\.body\(\) != b""/);
  assert.match(config, /context_structuring_enabled: bool = False/);
  assert.match(config, /app_env in \{"staging", "production"\}/);
  assert.doesNotMatch(workerMain, /SyntheticContextStructuringAI|aria\.context\.structure\.v1/);
  assert.match(fake, /provider = "synthetic"/);
  assert.match(fake, /input_tokens=0/);
  assert.match(env, /^CONTEXT_STRUCTURING_ENABLED=false$/m);
  assert.match(railway, /CONTEXT_STRUCTURING_ENABLED=false/);
  assert.match(adr, /customer\s+content.*disabled/is);
  assert.match(adr, /Normal runtime composition installs deny-all/is);
  for (const value of [apiMain, router]) {
    assert.doesNotMatch(value, /OpenAI|Gemini|OPENAI_API_KEY|GEMINI_API_KEY/);
  }
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

test("controlled E2E crosses HTTP, durable Relay, Celery mapping and synthetic Worker only", async () => {
  const prepare = await read("tests/e2e/prepare_context_structuring_command.py");
  const complete = await read("tests/e2e/complete_context_structuring_command.py");
  const runner = await read("tests/e2e/run-context-structuring-controlled.ps1");

  assert.match(prepare, /client\.post\(path, headers=headers\)/);
  assert.match(prepare, /ExplicitSyntheticContextStructuringProjects/);
  assert.match(complete, /DurableOutboxRelay/);
  assert.match(complete, /CeleryOutboxPublisher/);
  assert.match(complete, /ContextStructuringConsumer/);
  assert.match(complete, /SyntheticContextStructuringAI/);
  assert.match(complete, /current_context_version.*items/s);
  assert.match(runner, /TEST_DATABASE_URL/);
  assert.match(prepare, /aria_0072_test/);
  assert.match(complete, /aria_0072_test/);
  for (const value of [prepare, complete, runner]) {
    assert.doesNotMatch(value, /OPENAI_API_KEY|GEMINI_API_KEY|customer_content/);
  }
});
