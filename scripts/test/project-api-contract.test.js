import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("OpenAPI exposes only the approved Account Discovery and Project contracts", async () => {
  const contract = await read("packages/contracts/openapi.yaml");

  assert.match(contract, /\/accounts:/);
  assert.doesNotMatch(contract, /\/account-contexts:/);
  assert.match(contract, /\/projects:/);
  assert.match(contract, /Idempotency-Key/);
  assert.match(contract, /IDEMPOTENCY_CONFLICT/);
  assert.match(contract, /VERSION_CONFLICT/);
  assert.doesNotMatch(contract, /description:\s*\{[^\n]*Project/i);
});

test("Account discovery is pre-tenant and projects use tenant authorization", async () => {
  const accounts = await read("apps/api/app/api/routers/accounts.py");
  const projects = await read("apps/api/app/api/routers/projects.py");

  assert.match(accounts, /require_authenticated_identity/);
  assert.doesNotMatch(accounts, /require_tenant_context|X-Account-ID/);
  assert.match(projects, /require_tenant_context/);
  assert.match(projects, /Idempotency-Key/);
});

test("Project persistence enforces transactional idempotency and keyset ordering", async () => {
  const repository = await read(
    "apps/api/app/modules/projects/infrastructure/repository.py"
  );
  const migration = await read(
    "apps/api/migrations/versions/0003_project_create_idempotency.py"
  );

  assert.match(repository, /reserve_create/);
  assert.match(repository, /created_at\.desc\(\)[\s\S]*id\.desc\(\)/);
  assert.doesNotMatch(repository, /\.offset\(/);
  assert.match(migration, /project_create_requests/);
  assert.match(
    migration,
    /deferrable=True,\s*initially=["']DEFERRED["']/
  );
  assert.match(
    migration,
    /PrimaryKeyConstraint[\s\S]*account_id[\s\S]*idempotency_key/
  );
});

test("Project API is title-only for PATCH and soft-delete safe", async () => {
  const router = await read("apps/api/app/api/routers/projects.py");
  const repository = await read(
    "apps/api/app/modules/projects/infrastructure/repository.py"
  );

  assert.match(router, /expected_updated_at/);
  const updateRequest = router.match(
    /class UpdateProjectRequest[\s\S]*?class ProjectResponse/
  )?.[0];
  assert.ok(updateRequest);
  assert.doesNotMatch(updateRequest, /status/);
  assert.match(repository, /expected_updated_at/);
  assert.match(repository, /deleted_at\.is_\(None\)/);
  assert.match(repository, /soft_delete/);
});
