import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("account bootstrap preserves API/Application/Infrastructure layering", async () => {
  const dependency = await read("apps/api/app/api/dependencies/account_bootstrap.py");
  const useCase = await read("apps/api/app/modules/identity/application/account_bootstrap.py");
  const repository = await read(
    "apps/api/app/modules/identity/infrastructure/account_bootstrap.py"
  );

  assert.match(dependency, /Depends\(require_authenticated_identity\)/);
  assert.match(dependency, /bootstrapper\.execute\(identity\)/);
  assert.doesNotMatch(dependency, /sqlalchemy|AsyncSession|\bselect\s*\(/i);
  assert.doesNotMatch(useCase, /fastapi|sqlalchemy|supabase/i);
  assert.match(repository, /sqlalchemy/i);
});

test("account bootstrap has the approved implicit route and logging contract", async () => {
  const dependency = await read("apps/api/app/api/dependencies/account_bootstrap.py");
  const main = await read("apps/api/app/main.py");
  const openApi = await read("packages/contracts/openapi.yaml");
  const combinedRoutes = `${main}\n${openApi}`;

  for (const event of [
    "account.bootstrap_started",
    "account.bootstrap_completed",
    "account.bootstrap_failed",
    "account.bootstrap_resolved"
  ]) {
    assert.match(dependency, new RegExp(event.replaceAll(".", "\\.")));
  }
  assert.doesNotMatch(combinedRoutes, /["']\/(?:api\/v1\/)?(?:bootstrap|me)["']/i);
  assert.doesNotMatch(dependency, /profile_data|email|credentials|\.subject/);
});

test("M001 enforces the approved Profile and Membership schema", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0001_identity_projection.py"
  );
  const pyproject = await read("apps/api/pyproject.toml");

  assert.match(pyproject, /"alembic==1\.19\.0"/);
  assert.match(migration, /server_default=sa\.text\("gen_random_uuid\(\)"\)/);
  assert.match(migration, /"locale"[\s\S]*server_default="fa-IR"/);
  assert.doesNotMatch(migration, /["']email["']/i);
  assert.match(migration, /status IN \('active','invited','suspended'\)/);
  assert.doesNotMatch(migration, /disabled/);
  assert.match(migration, /UniqueConstraint\(\s*"account_id", "user_id"/);
  for (const table of ["accounts", "profiles", "account_memberships"]) {
    assert.match(migration, new RegExp(`ALTER TABLE ${table} ENABLE ROW LEVEL SECURITY`));
  }
  assert.doesNotMatch(migration, /CREATE POLICY|GRANT (?:SELECT|INSERT|UPDATE|DELETE)/i);
});

test("CI provisions the documented real PostgreSQL integration target", async () => {
  const workflow = await read(".github/workflows/ci.yml");

  assert.match(workflow, /services:\s*\n\s+postgres:/);
  assert.match(workflow, /image: postgres:16-alpine/);
  assert.match(workflow, /TEST_DATABASE_URL:/);
});
