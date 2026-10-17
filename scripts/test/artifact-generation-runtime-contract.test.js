import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("0100 freezes identifiers, identifier-only envelope and disabled automatic retry", async () => {
  const application = await read("apps/worker/app/application/artifact_generation_runtime.py");
  const task = await read("apps/worker/app/infrastructure/queue/artifact_generation_task.py");
  const publisher = await read("apps/worker/app/infrastructure/queue/outbox_publisher.py");
  assert.match(application, /artifact_generation/);
  assert.match(application, /artifact\.generation_requested\.v1/);
  assert.match(application, /aria\.artifact\.generate\.v1/);
  assert.match(task, /autoretry_for=\(\)/);
  assert.match(publisher, /ARTIFACT_GENERATION_EVENT_TYPE/);
});

test("0100 uses a fixed no-shell builder and create-or-verify storage", async () => {
  const builder = await read("apps/worker/app/infrastructure/artifact_builder.py");
  const storage = await read("apps/worker/app/infrastructure/artifact_storage.py");
  assert.match(builder, /create_subprocess_exec/);
  assert.doesNotMatch(builder, /create_subprocess_shell|shell=True/);
  assert.match(builder, /stdout=asyncio\.subprocess\.DEVNULL/);
  assert.match(storage, /IfNoneMatch="\*"/);
  assert.match(storage, /ARTIFACT_STORAGE_CONFLICT/);
});

test("0100 contract reserves checkpoint, active-generation and stale guards", async () => {
  const docs = await read("docs/adr/ADR-087-synthetic-artifact-generation-runtime.md");
  const migration = await read(
    "apps/api/migrations/versions/0039_artifact_generation_runtime.py",
  );
  assert.match(docs, /checkpoint_ref/);
  assert.match(docs, /checkpoint_hash/);
  assert.match(docs, /one\s+active generation/i);
  assert.match(docs, /ARTIFACT_GENERATION_STALE/);
  assert.match(docs, /WORKER-CROSS-TENANT-001/);
  assert.match(migration, /SECURITY DEFINER/);
  assert.match(migration, /SET search_path=''/);
  assert.match(migration, /GRANT EXECUTE ON FUNCTION aria_internal/);
  assert.doesNotMatch(
    migration,
    /GRANT (?:SELECT|INSERT|UPDATE|DELETE|ALL).*artifact_versions.*TO aria_worker/,
  );
});
