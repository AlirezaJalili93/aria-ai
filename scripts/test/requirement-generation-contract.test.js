import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("I02 uses the shared provider-neutral generation boundary", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/requirements_generation.py",
  );
  const worker = await read("apps/worker/app/application/requirements_generation.py");

  assert.match(application, /AIExecutionPort/);
  assert.match(application, /UsageLedger/);
  assert.match(application, /RequirementRepairPolicy/);
  assert.match(application, /max_repairs not in \(0, 1\)/);
  assert.match(worker, /aria_backend_application\.requirements_generation/);
  assert.doesNotMatch(application, /openai|anthropic|gemini|google\.genai|redis|celery/i);
});

test("I02 enforces exact snapshots, bounded merge, replay and atomic outbox", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/requirements_generation.py",
  );
  const repository = await read(
    "apps/api/app/modules/requirements/infrastructure/generation_repository.py",
  );
  const migration = await read("apps/api/migrations/versions/0012_requirement_generation.py");

  assert.match(application, /CONTEXT_SNAPSHOT_CHANGED/);
  assert.match(application, /current_revisions.*command\.context_item_revisions/s);
  assert.match(application, /DUPLICATE_CLASSIFICATION_CONFLICT/);
  assert.match(application, /_stable_union/);
  assert.match(application, /requirements\.replay_served/);
  assert.match(repository, /LOCK TABLE context_items IN SHARE MODE/);
  assert.match(repository, /JobModel\.status\.in_\(\("succeeded", "failed"\)\)/);
  assert.match(repository, /JobModel\.account_id == account_id/);
  assert.match(repository, /JobModel\.project_id == project_id/);
  assert.match(repository, /requirement\.conflict_detected/);
  assert.match(migration, /is_unsupported/);
  assert.match(migration, /generation_job_id/);
  assert.match(migration, /ix_requirements_account_project_generation_job/);
  assert.doesNotMatch(migration, /unique=True/);
  assert.doesNotMatch(migration, /requirement_generation_results/);
});

test("I02 keeps deferred surfaces and sensitive values out", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/requirements_generation.py",
  );
  const migration = await read("apps/api/migrations/versions/0012_requirement_generation.py");
  const main = await read("apps/api/app/main.py");

  assert.doesNotMatch(migration, /conflict_table|requirement_conflicts|gaps/i);
  assert.doesNotMatch(main, /requirement_generation.*router|generate_requirements_router/i);
  assert.doesNotMatch(
    application,
    /event_logger\.emit\([^)]*(candidate\.title|candidate\.description|source_refs|snapshot\.items)/s,
  );
});
