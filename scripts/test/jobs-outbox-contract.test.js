import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("logical M008 uses the current Jobs and Outbox dictionary", async () => {
  const migration = await read("apps/api/migrations/versions/0005_jobs_outbox.py");

  assert.match(migration, /revision:\s*str\s*=\s*["']0005_jobs_outbox["']/);
  assert.match(migration, /["']jobs["']/);
  assert.match(migration, /["']outbox_events["']/);
  assert.match(migration, /job_type/);
  assert.match(migration, /attempt_count/);
  assert.match(migration, /payload_ref/);
  assert.match(migration, /finished_at/);
  assert.match(migration, /queued','running','succeeded','failed','cancelled/);
  assert.match(migration, /pending','published','failed/);
  assert.doesNotMatch(migration, /input_ref|output_ref|attempt_no/);
});

test("Outbox payload is immutable and Data API authority remains fail closed", async () => {
  const migration = await read("apps/api/migrations/versions/0005_jobs_outbox.py");

  assert.match(migration, /prevent_outbox_payload_mutation/);
  assert.match(migration, /OLD\.payload IS DISTINCT FROM NEW\.payload/);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /REVOKE ALL PRIVILEGES/);
});

test("Jobs boundaries keep Domain independent and transaction ownership in Application", async () => {
  const domain = await read("apps/api/app/modules/jobs/domain/job.py");
  const application = await read("apps/api/app/modules/jobs/application/schedule_job.py");
  const repository = await read("apps/api/app/modules/jobs/infrastructure/repository.py");

  assert.doesNotMatch(domain, /fastapi|sqlalchemy|supabase|redis|aria_observability/i);
  assert.doesNotMatch(application, /fastapi|sqlalchemy|supabase|redis/i);
  assert.match(application, /unit_of_work\.jobs\.add/);
  assert.match(application, /unit_of_work\.outbox\.add/);
  assert.match(application, /unit_of_work\.commit/);
  assert.match(repository, /sqlalchemy/i);
});
