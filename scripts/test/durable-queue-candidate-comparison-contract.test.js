import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");
const dramatiqRoot = "evals/durable-queue/dramatiq";
const rqRoot = "evals/durable-queue/rq";

test("Dramatiq and RQ candidates remain evaluation-only beside the exact runtime Worker pin", async () => {
  const [dramatiqProject, dramatiqLock, rqProject, rqLock, workerProject, plan] =
    await Promise.all([
      read(`${dramatiqRoot}/pyproject.toml`),
      read(`${dramatiqRoot}/uv.lock`),
      read(`${rqRoot}/pyproject.toml`),
      read(`${rqRoot}/uv.lock`),
      read("apps/worker/pyproject.toml"),
      read("docs/architecture/durable-queue-evaluation-plan.md")
    ]);

  assert.match(dramatiqProject, /dramatiq\[redis\]==2\.2\.1/);
  assert.match(dramatiqLock, /name = "dramatiq"[\s\S]*version = "2\.2\.1"/);
  assert.match(rqProject, /rq==2\.12\.0/);
  assert.match(rqLock, /name = "rq"[\s\S]*version = "2\.12\.0"/);
  assert.match(workerProject, /celery\[redis\]==5\.6\.3/);
  assert.doesNotMatch(workerProject, /dramatiq|\brq\b/i);
  assert.match(plan, /Celery 5\.6\.3 selected in accepted ADR-015/i);
});

test("candidate Compose projects cannot collide with each other or hosted infrastructure", async () => {
  const [dramatiqCompose, rqCompose] = await Promise.all([
    read(`${dramatiqRoot}/compose.yaml`),
    read(`${rqRoot}/compose.yaml`)
  ]);

  assert.match(dramatiqCompose, /name:\s*aria-dramatiq-queue-eval/);
  assert.match(dramatiqCompose, /127\.0\.0\.1:16380:6379/);
  assert.match(rqCompose, /name:\s*aria-rq-queue-eval/);
  assert.match(rqCompose, /127\.0\.0\.1:16381:6379/);
  for (const compose of [dramatiqCompose, rqCompose]) {
    assert.match(compose, /healthcheck:/);
    assert.match(compose, /QUEUE_EVAL_REDIS_PASSWORD:\s*\$\{QUEUE_EVAL_REDIS_PASSWORD:\?required\}/);
    assert.match(compose, /entrypoint:\s*\["python", "-m", "queue_eval\.cli"\]/);
    assert.doesNotMatch(compose, /upstash|railway|production|staging/i);
  }
});

test("Dramatiq candidate makes loss recovery and product-default boundaries explicit", async () => {
  const [candidate, runner, readme] = await Promise.all([
    read(`${dramatiqRoot}/queue_eval/app.py`),
    read(`${dramatiqRoot}/run-evaluation.ps1`),
    read(`${dramatiqRoot}/README.md`)
  ]);

  assert.match(candidate, /heartbeat_timeout=heartbeat_timeout_ms/);
  assert.match(candidate, /maintenance_chance=1_000_000/);
  assert.match(candidate, /max_retries=0/);
  assert.match(runner, /docker compose kill queue-eval-worker/);
  assert.match(runner, /worker-absent/);
  assert.match(runner, /--max-attempts 0/);
  assert.match(runner, /duplicate-delivery/);
  assert.match(runner, /delayed-delivery/);
  assert.match(runner, /idle-command-delta/);
  assert.match(readme, /experiment fixtures, not[\s\S]*production defaults/i);
});

test("RQ candidate rejects pickle and measures native retry and abandoned-job recovery", async () => {
  const [candidate, worker, runner, readme] = await Promise.all([
    read(`${rqRoot}/queue_eval/app.py`),
    read(`${rqRoot}/queue_eval/worker.py`),
    read(`${rqRoot}/run-evaluation.ps1`),
    read(`${rqRoot}/README.md`)
  ]);

  assert.match(candidate, /serializer=JSONSerializer/);
  assert.match(worker, /serializer=JSONSerializer/);
  assert.match(worker, /maintenance_interval=/);
  assert.match(worker, /job_monitoring_interval=/);
  assert.match(worker, /worker_ttl=/);
  assert.match(runner, /--fail-first-attempt/);
  assert.match(runner, /docker compose kill queue-eval-worker/);
  assert.match(runner, /abandoned-job-recovery-may-take-about-61-seconds/);
  assert.match(runner, /--max-attempts 0/);
  assert.match(runner, /delayed-delivery/);
  assert.match(readme, /does not manipulate Redis time or registry scores/i);
});

test("both runners use PowerShell-compatible random credentials and isolated volume reset", async () => {
  const runners = await Promise.all([
    read(`${dramatiqRoot}/run-evaluation.ps1`),
    read(`${rqRoot}/run-evaluation.ps1`)
  ]);

  for (const runner of runners) {
    assert.match(runner, /RandomNumberGenerator\]::Create\(\)/);
    assert.doesNotMatch(runner, /RandomNumberGenerator\]::GetBytes\(/);
    assert.doesNotMatch(runner, /Convert\]::ToHexString/);
    assert.match(runner, /docker compose down --volumes --remove-orphans/);
  }
});

test("comparison records the explicitly accepted evidence-backed recommendation", async () => {
  const [decision, plan, workerProject, validator] = await Promise.all([
    read("docs/adr/ADR-015-durable-queue-framework.md"),
    read("docs/architecture/durable-queue-evaluation-plan.md"),
    read("apps/worker/pyproject.toml"),
    read("scripts/validate-architecture.mjs")
  ]);

  assert.match(decision, /Status: Accepted/);
  assert.match(decision, /Accepted by:[\s\S]*owner response/);
  assert.match(decision, /Select Celery 5\.6\.3/);
  assert.match(decision, /Celery 5\.6\.3=`36`[\s\S]*Dramatiq 2\.2\.1=`141`[\s\S]*RQ 2\.12\.0=`249`/);
  assert.match(plan, /Celery 5\.6\.3 selected in accepted ADR-015/);
  assert.match(plan, /owner accepted that framework\/version decision/);
  assert.match(workerProject, /celery\[redis\]==5\.6\.3/);
  assert.doesNotMatch(workerProject, /dramatiq|\brq\b/i);
  assert.match(validator, /"celery\\\[redis\\\]==5\\\.6\\\.3"/);
  assert.match(validator, /API deployable must remain Queue-framework neutral/);
  assert.match(validator, /accepted ADR-015/);
});
