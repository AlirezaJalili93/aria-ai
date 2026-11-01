import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

test("0080 freezes the pre-Provider hard-kill and same-Job redelivery contract", () => {
  const adr = read("docs/adr/ADR-066-worker-restart-redelivery-gate.md");
  const harness = read("tests/e2e/controlled_worker_restart_runtime.py");
  const runner = read("tests/e2e/run-worker-restart-redelivery-controlled.ps1");
  const celery = read("apps/worker/app/infrastructure/queue/celery_runtime.py");

  assert.match(adr, /Status: Accepted/);
  assert.match(adr, /after Job preparation and before\s+AI invocation/);
  assert.match(adr, /Celery automatic task retry remains disabled/);
  assert.match(celery, /task_acks_late=True/);
  assert.match(celery, /task_reject_on_worker_lost=True/);
  assert.match(celery, /worker_prefetch_multiplier=1/);
  assert.match(harness, /await _block_until_process_death\(\)/);
  assert.match(harness, /register_context_structuring_task\(celery_app, consumer\)/);
  assert.match(harness, /autoretry_for != \(\)/);
  assert.match(harness, /SqlAlchemyUsageLedger\(engine\)/);
  assert.match(runner, /Stop-Process -Id \$process\.Id -Force/);
  assert.match(runner, /CONTROLLED_0080_GATE=PASS/);
});

test("0080 remains synthetic-only and outside Hosted Worker composition", () => {
  const adr = read("docs/adr/ADR-066-worker-restart-redelivery-gate.md");
  const hosted = read("apps/worker/app/main.py");
  assert.match(adr, /Customer\s+content, real or paid Providers, Hosted activation.*prohibited/s);
  assert.doesNotMatch(hosted, /register_context_structuring_task/);
});
