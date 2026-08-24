import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("staging migrations run only from main in a serialized protected environment", async () => {
  const workflow = await read(".github/workflows/staging-migrations.yml");

  assert.match(workflow, /workflow_dispatch:/);
  assert.match(workflow, /branches:\s*\[main\]/);
  assert.match(workflow, /github\.ref == 'refs\/heads\/main'/);
  assert.match(workflow, /environment:\s*staging/);
  assert.match(workflow, /group:\s*staging-database-migrations/);
  assert.match(workflow, /cancel-in-progress:\s*false/);
  assert.match(workflow, /permissions:\s*\n\s+contents:\s*read/);
});

test("staging migration credential remains an environment secret", async () => {
  const workflow = await read(".github/workflows/staging-migrations.yml");

  assert.match(workflow, /DATABASE_URL:\s*\$\{\{ secrets\.STAGING_DATABASE_URL \}\}/);
  assert.match(workflow, /test -n "\$\{DATABASE_URL:-\}"/);
  assert.doesNotMatch(workflow, /postgres(?:ql)?:\/\/[^$\s]/i);
  assert.doesNotMatch(workflow, /SUPABASE_ACCESS_TOKEN|SUPABASE_DB_PASSWORD|service_role/i);
});

test("the migration runner owns the database advisory lock and revision verification", async () => {
  const runner = await read("scripts/db/migrate.py");
  const workflow = await read(".github/workflows/staging-migrations.yml");

  assert.match(runner, /pg_try_advisory_lock\(hashtextextended/);
  assert.match(runner, /pg_advisory_unlock\(hashtextextended/);
  assert.match(runner, /finally:/);
  assert.match(runner, /command\.upgrade/);
  assert.match(runner, /get_current_head/);
  assert.match(runner, /SELECT version_num FROM alembic_version/);
  assert.match(runner, /database\.migration_completed revision=%s duration_ms=%d/);
  assert.match(workflow, /python scripts\/db\/migrate\.py/);
  assert.doesNotMatch(workflow, /supabase\/setup-cli|supabase db push/i);
});

test("pull-request CI keeps proving the fresh PostgreSQL migration chain", async () => {
  const ci = await read(".github/workflows/ci.yml");

  assert.match(ci, /pull_request:/);
  assert.match(ci, /image: postgres:16-alpine/);
  assert.match(ci, /DATABASE_URL:/);
  assert.match(ci, /npm run quality/);
});
