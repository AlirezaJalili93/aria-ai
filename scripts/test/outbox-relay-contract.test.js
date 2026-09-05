import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("Outbox relay keeps queue transport behind an application port", async () => {
  const ports = await read("apps/api/app/modules/jobs/application/ports.py");
  const relay = await read("apps/api/app/modules/jobs/application/outbox_relay.py");

  assert.match(ports, /class QueuePublisher\(Protocol\)/);
  assert.match(ports, /async def publish\(self, event: OutboxEvent\)/);
  assert.match(relay, /QueuePublisher/);
  assert.doesNotMatch(relay, /celery|redis|kombu|fastapi/i);
});

test("Outbox relay publishes before the separate published-state transaction", async () => {
  const relay = await read("apps/api/app/modules/jobs/application/outbox_relay.py");

  assert.match(relay, /await self\._publisher\.publish\(event\)/);
  assert.match(relay, /mark_published/);
  assert.match(relay, /outbox\.publish_succeeded/);
  assert.match(relay, /outbox\.mark_published_failed/);
  assert.match(relay, /outbox\.republished/);
});

test("Outbox relay logging excludes the payload", async () => {
  const relay = await read("apps/api/app/modules/jobs/application/outbox_relay.py");
  const observability = await read("packages/observability/src/aria_observability/logging.py");

  assert.doesNotMatch(relay, /payload=/);
  assert.match(observability, /outbox_event_id/);
  assert.match(observability, /aggregate_id/);
  assert.match(observability, /aggregate_type/);
});
