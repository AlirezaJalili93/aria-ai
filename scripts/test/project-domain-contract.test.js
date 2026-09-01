import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("M002 implements the approved Project data contract", async () => {
  const migration = await read("apps/api/migrations/versions/0002_projects.py");

  assert.match(migration, /revision:\s*str\s*=\s*["']0002_projects["']/);
  assert.match(migration, /down_revision:\s*str\s*\|\s*None\s*=\s*["']0001_identity_access_hardening["']/);
  assert.match(migration, /["']owner_id["'][\s\S]*profiles\.user_id/);
  assert.match(migration, /["']current_context_version["'][\s\S]*server_default=["']0["']/);
  assert.match(migration, /current_context_version >= 0/);
  assert.match(migration, /draft','active','awaiting_approval','approved','generating','delivered','archived/);
  assert.match(migration, /["']deleted_at["'][\s\S]*nullable=True/);
  assert.match(migration, /ix_projects_account_id_created_at/);
  assert.match(migration, /ix_projects_account_id_status/);
  assert.match(migration, /ix_projects_account_id_project_type/);
  assert.match(migration, /ALTER TABLE projects ENABLE ROW LEVEL SECURITY/);
});

test("M002 owns database-managed updated_at without opening Data API authority", async () => {
  const migration = await read("apps/api/migrations/versions/0002_projects.py");

  assert.match(migration, /CREATE OR REPLACE FUNCTION public\.set_updated_at/);
  assert.match(migration, /\("accounts", "profiles", "projects"\)/);
  assert.match(migration, /BEFORE UPDATE ON \{table_name\}/);
  assert.match(migration, /REVOKE ALL ON FUNCTION public\.set_updated_at\(\) FROM PUBLIC/);
  assert.doesNotMatch(migration, /GRANT ALL/i);
});

test("Project module preserves Domain/Application/Infrastructure boundaries", async () => {
  const domain = await read("apps/api/app/modules/projects/domain/project.py");
  const application = await read(
    "apps/api/app/modules/projects/application/project_service.py"
  );
  const repository = await read(
    "apps/api/app/modules/projects/infrastructure/repository.py"
  );

  assert.doesNotMatch(domain, /fastapi|sqlalchemy|supabase|aria_observability/i);
  assert.doesNotMatch(application, /fastapi|sqlalchemy|supabase/i);
  assert.match(repository, /sqlalchemy/i);
  assert.match(application, /membership_status\s*!=\s*["']active["']/);
});

test("ordinary Project repository reads are soft-delete and tenant scoped", async () => {
  const repository = await read(
    "apps/api/app/modules/projects/infrastructure/repository.py"
  );
  const application = await read(
    "apps/api/app/modules/projects/application/project_service.py"
  );

  assert.match(repository, /ProjectModel\.account_id\s*==\s*account_id/);
  assert.match(repository, /ProjectModel\.deleted_at\.is_\(None\)/);
  assert.match(repository, /get_including_deleted/);
  assert.match(application, /project\.created/);
  assert.match(application, /project\.updated/);
  assert.match(application, /project\.archived/);
  assert.match(application, /project\.soft_deleted/);
  assert.match(application, /project\.repository_failed/);
  assert.doesNotMatch(application, /title=.*(?:emit|logger)|profile_data|raw_sub|jwt/i);
});
