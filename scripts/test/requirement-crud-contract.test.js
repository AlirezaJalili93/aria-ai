import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("I03 exposes only the approved tenant-scoped Requirement surface", async () => {
  const router = await read("apps/api/app/api/routers/requirements.py");
  const openapi = await read("packages/contracts/openapi.yaml");
  const main = await read("apps/api/app/main.py");

  assert.match(router, /prefix="\/projects\/\{project_id\}\/requirements"/);
  assert.match(router, /Idempotency-Key/);
  assert.match(router, /expected_updated_at/);
  assert.match(router, /acceptance_note_set/);
  assert.doesNotMatch(router, /generation_job_id=requirement\.generation_job_id/);
  assert.doesNotMatch(router, /duplicate_group_key=requirement\.duplicate_group_key/);
  assert.match(openapi, /operationId: createManualRequirement/);
  assert.match(openapi, /operationId: listRequirements/);
  assert.match(openapi, /operationId: updateRequirement/);
  assert.match(openapi, /operationId: deactivateDraftRequirement/);
  assert.match(main, /create_requirements_router/);
});

test("I03 migration and repository preserve soft lifecycle and tenant isolation", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0013_requirement_crud.py",
  );
  const repository = await read(
    "apps/api/app/modules/requirements/infrastructure/repository.py",
  );
  const application = await read(
    "apps/api/app/modules/requirements/application/requirement_crud_service.py",
  );

  assert.match(migration, /acceptance_note/);
  assert.match(migration, /ix_requirements_account_project_created/);
  assert.match(repository, /RequirementModel\.account_id == account_id/);
  assert.match(repository, /RequirementModel\.project_id == project_id/);
  assert.match(repository, /RequirementModel\.status\.not_in\(\("removed", "superseded"\)\)/);
  assert.doesNotMatch(repository, /delete\(RequirementModel\)/);
  assert.match(application, /current_context_version < 1/);
  assert.match(application, /next_status = "draft"/);
  assert.match(application, /current\.status != "draft"/);
});

test("I03 structured events never log Requirement content", async () => {
  const application = await read(
    "apps/api/app/modules/requirements/application/requirement_crud_service.py",
  );
  const emitted = application.slice(application.indexOf('"requirement.added"'));

  assert.match(emitted, /requirement\.added/);
  assert.match(emitted, /requirement\.edited/);
  assert.match(emitted, /requirement\.confirmed/);
  assert.match(emitted, /requirement\.removed/);
  assert.doesNotMatch(
    emitted,
    /persisted\.(title|description|acceptance_note|source_refs)/,
  );
});
