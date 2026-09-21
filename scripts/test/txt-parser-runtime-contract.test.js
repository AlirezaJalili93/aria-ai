import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("TXT Parser consumer keeps Queue input minimal and PostgreSQL authoritative", async () => {
  const runtime = await read("apps/worker/app/application/txt_parser_consumer.py");
  const adr = await read("docs/adr/ADR-051-txt-parser-consumer-recovery.md");

  for (const field of ["message_version", "outbox_event_id", "job_id"]) {
    assert.match(runtime, new RegExp(field));
  }
  assert.match(adr, /Account, Project, Source and Version authority is loaded from PostgreSQL/);
  assert.doesNotMatch(runtime, /celery|boto3|sqlalchemy|asyncpg/i);
});

test("TXT hash, automatic-retry and durable Relay boundaries are explicit", async () => {
  const adr = await read("docs/adr/ADR-051-txt-parser-consumer-recovery.md");
  const workerReadme = await read("apps/worker/app/tasks/README.md");
  const taskAdapter = await read("apps/worker/app/infrastructure/queue/parser_task.py");

  assert.match(adr, /lowercase SHA-256/);
  assert.match(adr, /automatic retry is disabled/);
  const relayAdr = await read("docs/adr/ADR-057-durable-outbox-delivery-runtime.md");
  assert.match(relayAdr, /Hosted Relay activation remains disabled/);
  assert.match(workerReadme, /aria\.context\.parse\.v1/);
  assert.match(taskAdapter, /register_txt_parser_task/);
});

test("Worker storage and DB details remain Infrastructure concerns", async () => {
  const consumer = await read("apps/worker/app/application/txt_parser_consumer.py");
  const storage = await read("apps/worker/app/infrastructure/storage/supabase_s3.py");
  const persistence = await read("apps/worker/app/infrastructure/db/txt_parser_runtime.py");

  assert.doesNotMatch(consumer, /boto3|botocore|sqlalchemy|asyncpg/i);
  assert.match(storage, /get_object/);
  assert.match(persistence, /pg_try_advisory_lock/);
  assert.match(persistence, /context_source_versions/);
  assert.match(persistence, /jobs/);
});

test("Parser telemetry uses source_version_id and forbids content-bearing fields", async () => {
  const parser = await read("apps/worker/app/application/context_parser.py");
  const consumer = await read("apps/worker/app/application/txt_parser_consumer.py");

  assert.match(parser, /source_version_id/);
  assert.doesNotMatch(parser, /source_id=str\(source_version\.id\)/);
  for (const call of consumer.matchAll(/\.emit\(([\s\S]*?)\n\s*\)/g)) {
    assert.doesNotMatch(
      call[1],
      /raw_text=|canonical_text=|object_key=|filename=|error_message=/,
    );
  }
});
