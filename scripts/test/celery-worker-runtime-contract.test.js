import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const read = (file) => readFile(file, "utf8");

async function pythonFiles(root) {
  const entries = await readdir(root, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map(async (entry) => {
      const target = path.join(root, entry.name);
      if (entry.isDirectory()) return pythonFiles(target);
      return entry.isFile() && entry.name.endsWith(".py") ? [target] : [];
    })
  );
  return nested.flat();
}

test("Worker alone adopts the exact accepted Celery Redis dependency", async () => {
  const [workerProject, workerLock, apiProject] = await Promise.all([
    read("apps/worker/pyproject.toml"),
    read("apps/worker/uv.lock"),
    read("apps/api/pyproject.toml")
  ]);

  assert.match(workerProject, /"celery\[redis\]==5\.6\.3"/);
  assert.match(workerLock, /name = "celery"[\s\S]*version = "5\.6\.3"/);
  assert.doesNotMatch(apiProject, /celery|dramatiq|\brq\b/i);
});

test("Queue runtime configuration is explicit and default-free", async () => {
  const [config, example, railway] = await Promise.all([
    read("apps/worker/app/core/config.py"),
    read(".env.example"),
    read("infra/railway/README.md")
  ]);

  for (const name of ["QUEUE_NAME", "QUEUE_VISIBILITY_TIMEOUT_SECONDS", "WORKER_CONCURRENCY"]) {
    assert.match(example, new RegExp(`^${name}=$`, "m"));
    assert.match(railway, new RegExp(name));
  }
  assert.match(config, /queue_name:\s*NonEmptyString \| None = None/);
  assert.match(config, /queue_visibility_timeout_seconds:\s*PositiveInteger \| None = None/);
  assert.match(config, /worker_concurrency:\s*PositiveInteger \| None = None/);
  assert.match(config, /require_queue_runtime_configuration/);
});

test("Celery adapter enforces the accepted transport boundary only", async () => {
  const adapter = await read("apps/worker/app/infrastructure/queue/celery_runtime.py");

  assert.match(adapter, /task_serializer="json"/);
  assert.match(adapter, /result_serializer="json"/);
  assert.match(adapter, /accept_content=\["json"\]/);
  assert.match(adapter, /task_acks_late=True/);
  assert.match(adapter, /task_reject_on_worker_lost=True/);
  assert.match(adapter, /worker_prefetch_multiplier=1/);
  assert.match(adapter, /result_backend=None/);
  assert.match(adapter, /task_ignore_result=True/);
  assert.match(adapter, /visibility_timeout/);
  assert.doesNotMatch(adapter, /task_(?:soft_)?time_limit|autoretry_for|max_retries|retry_backoff/);
});

test("Celery imports stay in Infrastructure and the composition root reports truthfully", async () => {
  const files = await pythonFiles("apps/worker/app");
  const contents = await Promise.all(files.map(async (file) => [file, await read(file)]));
  const celeryImports = contents.filter(([, body]) => /^from celery\b|^import celery\b/m.test(body));
  const main = await read("apps/worker/app/main.py");

  assert.equal(celeryImports.length, 1);
  assert.match(celeryImports[0][0].replaceAll("\\", "/"), /\/infrastructure\/queue\/celery_runtime\.py$/);
  assert.match(main, /WorkerBootstrap\([\s\S]*queue_adapter_configured=True/);
  assert.match(main, /queue_runtime\.run\(\)/);
  assert.doesNotMatch(main, /wait_forever/);
});

test("S1-E02 adds no business task wrapper before S1-E04", async () => {
  const [tasksReadme, plan] = await Promise.all([
    read("apps/worker/app/tasks/README.md"),
    read("docs/architecture/durable-queue-evaluation-plan.md")
  ]);

  assert.match(tasksReadme, /S1-E04/);
  assert.match(plan, /retry\/backoff[\s\S]*require a documented decision/i);
});
