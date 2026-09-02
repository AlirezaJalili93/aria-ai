import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("logical M003 implements the approved Context Source data contract", async () => {
  const migration = await read("apps/api/migrations/versions/0004_context_sources.py");

  assert.match(migration, /revision:\s*str\s*=\s*["']0004_context_sources["']/);
  assert.match(migration, /["']context_sources["']/);
  assert.match(migration, /["']context_source_versions["']/);
  assert.match(migration, /uploaded','parsing','ready','failed','deleted/);
  assert.match(migration, /pending','parsing','ready','failed/);
  assert.match(migration, /version_no >= 1/);
  assert.match(migration, /canonical_text IS NOT NULL OR storage_ref IS NOT NULL/);
  assert.match(migration, /source_id[\s\S]*account_id[\s\S]*project_id[\s\S]*context_sources/);
  assert.match(migration, /ondelete=["']RESTRICT["']/);
  assert.doesNotMatch(migration, /current_version_no|archived_at|context_source_id/);
});

test("ready Version history is protected and current Version is derived", async () => {
  const migration = await read("apps/api/migrations/versions/0004_context_sources.py");
  const repository = await read(
    "apps/api/app/modules/context/infrastructure/repository.py"
  );

  assert.match(migration, /prevent_ready_context_source_version_mutation/);
  assert.match(migration, /OLD\.parse_status = 'ready'/);
  assert.match(repository, /ContextSourceVersionModel\.parse_status == ["']ready["']/);
  assert.match(repository, /ContextSourceVersionModel\.version_no\.desc\(\)/);
});

test("Context module preserves boundaries and S1-D01 enables text only", async () => {
  const domain = await read("apps/api/app/modules/context/domain/context_source.py");
  const application = await read(
    "apps/api/app/modules/context/application/context_source_service.py"
  );
  const repository = await read(
    "apps/api/app/modules/context/infrastructure/repository.py"
  );

  assert.doesNotMatch(domain, /fastapi|sqlalchemy|supabase|aria_observability/i);
  assert.doesNotMatch(application, /fastapi|sqlalchemy|supabase/i);
  assert.match(repository, /sqlalchemy/i);
  assert.match(application, /APPLICATION_SOURCE_TYPES/);
  assert.match(application, /context_source\.created/);
  assert.match(application, /context_source\.deleted/);
  assert.match(application, /f["']context_source_version\.\{outcome\}["']/);
  assert.match(application, /_emit_version_event\(["']created["']/);
  assert.match(application, /_emit_version_event\(["']ready["']/);
  assert.match(application, /_emit_version_event\(["']failed["']/);
  assert.doesNotMatch(application, /raw_text=.*(?:emit|logger)|canonical_text=.*(?:emit|logger)|storage_ref=.*(?:emit|logger)|metadata=.*(?:emit|logger)/i);
});

test("ordinary Source reads are tenant scoped and exclude deleted lifecycle rows", async () => {
  const repository = await read(
    "apps/api/app/modules/context/infrastructure/repository.py"
  );

  assert.match(repository, /ContextSourceModel\.account_id == account_id/);
  assert.match(repository, /ContextSourceModel\.project_id == project_id/);
  assert.match(repository, /ContextSourceModel\.status != ["']deleted["']/);
  assert.doesNotMatch(repository, /delete\(ContextSourceModel\)|session\.delete/);
});
