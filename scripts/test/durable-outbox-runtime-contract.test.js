import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("Outbox routing is explicit and only approved Job work reaches Celery", async () => {
  const migration = await read("apps/api/migrations/versions/0025_outbox_delivery_runtime.py");
  const publisher = await read("apps/worker/app/infrastructure/queue/outbox_publisher.py");
  const requirements = await read(
    "apps/api/app/modules/requirements/infrastructure/generation_repository.py",
  );

  assert.match(migration, /delivery_channel/);
  assert.match(migration, /job_queue/);
  assert.match(migration, /domain_event/);
  assert.match(publisher, /context_added\.v1/);
  assert.match(publisher, /aria\.context\.parse\.v1/);
  assert.match(publisher, /context\.structuring_requested\.v1/);
  assert.match(publisher, /aria\.context\.structure\.v1/);
  assert.match(requirements, /delivery_channel="domain_event"/);
  assert.doesNotMatch(publisher, /requirement\.conflict_detected/);
});

test("Relay freezes short claim, lease, polling and bounded backoff semantics", async () => {
  const application = await read("apps/worker/app/application/outbox_delivery.py");
  const repository = await read("apps/worker/app/infrastructure/db/outbox_delivery.py");

  assert.match(application, /OUTBOX_POLL_INTERVAL_SECONDS = 2/);
  assert.match(application, /OUTBOX_BATCH_SIZE = 20/);
  assert.match(application, /OUTBOX_LEASE_SECONDS = 30/);
  assert.match(application, /OUTBOX_BACKOFF_CAP_SECONDS = 60/);
  assert.match(repository, /FOR UPDATE SKIP LOCKED/);
  assert.match(repository, /blocked_unknown_event/);
  assert.match(repository, /claim_id=:claim_id/);
});

test("Worker artifact supports relay mode without hosted activation", async () => {
  const main = await read("apps/worker/app/main.py");
  const celery = await read("apps/worker/app/infrastructure/queue/celery_runtime.py");
  const railway = await read("infra/railway/README.md");

  assert.match(main, /values == \["relay"\]/);
  assert.match(main, /run_relay/);
  assert.match(celery, /task_publish_retry=False/);
  assert.match(railway, /no hosted Relay service\/process is activated/);
});

test("Relay logging code never emits payload or customer content", async () => {
  const application = await read("apps/worker/app/application/outbox_delivery.py");
  const adr = await read("docs/adr/ADR-057-durable-outbox-delivery-runtime.md");

  for (const call of application.matchAll(/\.emit\(([^)]*)\)/gs)) {
    assert.doesNotMatch(call[1], /payload=|customer_content=|raw_text=|canonical_text=/);
  }
  assert.match(adr, /never contain\s+payload or customer content/);
});
