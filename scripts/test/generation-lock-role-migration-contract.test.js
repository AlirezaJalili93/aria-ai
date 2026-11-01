import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const migrationPath =
  "apps/api/migrations/versions/0030_generation_input_row_locks.py";

test("generation lock owner creation is cluster-idempotent and fail-closed", async () => {
  const migration = await readFile(migrationPath, "utf8");

  assert.match(migration, /FROM pg_catalog\.pg_roles/);
  assert.match(migration, /rolname='aria_generation_lock_owner'/);
  assert.match(migration, /IF NOT FOUND THEN/);
  assert.match(migration, /CREATE ROLE aria_generation_lock_owner/);
  for (const attribute of [
    "rolcanlogin",
    "rolinherit",
    "rolsuper",
    "rolcreatedb",
    "rolcreaterole",
    "rolreplication",
    "rolbypassrls",
  ]) {
    assert.match(migration, new RegExp(attribute));
  }
  assert.match(migration, /generation lock owner role attributes rejected/);
  assert.doesNotMatch(migration, /ALTER ROLE aria_generation_lock_owner/);
});

test("generation lock owner downgrade preserves cross-database dependencies", async () => {
  const migration = await readFile(migrationPath, "utf8");

  assert.match(migration, /pg_catalog\.pg_shdepend/);
  assert.match(migration, /pg_catalog\.pg_database/);
  assert.match(migration, /dbid <> v_current_database_oid/);
  assert.match(migration, /DROP ROLE aria_generation_lock_owner/);
});
