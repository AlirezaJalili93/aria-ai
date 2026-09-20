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

test("TXT hash, automatic-retry and Scheduler boundaries are explicit", async () => {
  const adr = await read("docs/adr/ADR-051-txt-parser-consumer-recovery.md");
  const workerReadme = await read("apps/worker/app/tasks/README.md");
  const controlledRunner = await read("apps/worker/app/tasks/txt_parser.py");

  assert.match(adr, /lowercase SHA-256/);
  assert.match(adr, /automatic retry is disabled/);
  assert.match(adr, /Continuous Outbox relay scheduler/);
  assert.match(workerReadme, /Hosted automatic processing remains disabled/);
  assert.doesNotMatch(controlledRunner, /Celery|celery|register_/);
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
