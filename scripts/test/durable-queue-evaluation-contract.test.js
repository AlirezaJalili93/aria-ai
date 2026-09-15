import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");
const evaluationRoot = "evals/durable-queue/celery";

test("Celery evaluation is isolated and exactly pinned", async () => {
  const [candidateProject, workerProject, plan] = await Promise.all([
    read(`${evaluationRoot}/pyproject.toml`),
    read("apps/worker/pyproject.toml"),
    read("docs/architecture/durable-queue-evaluation-plan.md")
  ]);

  assert.match(candidateProject, /celery\[redis\]==5\.6\.3/);
  assert.match(workerProject, /celery\[redis\]==5\.6\.3/);
  assert.doesNotMatch(workerProject, /dramatiq|\brq\b/i);
  assert.match(plan, /Celery 5\.6\.3 selected in accepted ADR-015/i);
});

test("evaluation Compose stack is local, dedicated and bounded", async () => {
  const compose = await read(`${evaluationRoot}/compose.yaml`);

  assert.match(compose, /name:\s*aria-queue-eval/);
  assert.match(compose, /127\.0\.0\.1:16379:6379/);
  assert.match(compose, /healthcheck:/);
  assert.match(compose, /queue-eval-worker/);
  assert.match(compose, /entrypoint:\s*\["python", "-m", "queue_eval\.cli"\]/);
  assert.doesNotMatch(compose, /upstash|railway|production|staging/i);
});

test("candidate configuration exposes late-ack redelivery without product defaults", async () => {
  const candidate = await read(`${evaluationRoot}/queue_eval/app.py`);

  assert.match(candidate, /task_acks_late=True/);
  assert.match(candidate, /task_reject_on_worker_lost=True/);
  assert.match(candidate, /worker_prefetch_multiplier=1/);
  assert.match(candidate, /visibility_timeout/);
  assert.match(candidate, /task_serializer="json"/);
  assert.match(candidate, /accept_content=\["json"\]/);
});

test("runner covers worker absence, forced loss, duplicate delivery and idle usage", async () => {
  const runner = await read(`${evaluationRoot}/run-evaluation.ps1`);

  assert.match(runner, /RandomNumberGenerator\]::Create\(\)/);
  assert.doesNotMatch(runner, /RandomNumberGenerator\]::GetBytes\(/);
  assert.doesNotMatch(runner, /Convert\]::ToHexString/);
  assert.match(runner, /worker-absent/);
  assert.match(runner, /docker compose kill queue-eval-worker/);
  assert.match(runner, /forced-worker-loss/);
  assert.match(runner, /duplicate-delivery/);
  assert.match(runner, /idle-command-delta/);
});
