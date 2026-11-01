import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("Worker idempotency is a provider-neutral atomic Application port", async () => {
  const ports = await read("apps/worker/app/application/ports.py");
  const coordinator = await read("apps/worker/app/application/job_execution.py");

  assert.match(ports, /class JobExecutionGuard\(Protocol\)/);
  assert.match(ports, /async def acquire\(self, job_id: UUID\)/);
  assert.match(ports, /already_in_progress/);
  assert.match(ports, /already_completed/);
  assert.match(ports, /async def complete\(self, job_id: UUID\)/);
  assert.match(coordinator, /JobExecutionGuard/);
  assert.doesNotMatch(coordinator, /celery|redis|sqlalchemy|asyncpg|kombu/i);
});

test("Duplicate decisions suppress the handler and leave transport semantics deferred", async () => {
  const coordinator = await read("apps/worker/app/application/job_execution.py");
  const tasksReadme = await read("apps/worker/app/tasks/README.md");

  assert.match(coordinator, /already_completed/);
  assert.match(coordinator, /already_in_progress/);
  assert.match(coordinator, /worker\.job_duplicate_suppressed/);
  assert.match(coordinator, /worker\.job_already_completed/);
  assert.match(tasksReadme, /ACK|requeue|retry|transport/i);
});

test("Worker guard telemetry uses the approved safe event vocabulary", async () => {
  const coordinator = await read("apps/worker/app/application/job_execution.py");

  for (const eventName of [
    "worker.job_guard_acquired",
    "worker.job_duplicate_suppressed",
    "worker.job_already_completed",
    "worker.job_execution_started",
    "worker.job_execution_interrupted"
  ]) {
    assert.match(coordinator, new RegExp(eventName.replaceAll(".", "\\.")));
  }
  assert.doesNotMatch(coordinator, /payload=|prompt=|artifact|raw_input/i);
});
