import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("logical M005 implements the approved Requirement schema", async () => {
  const migration = await read("apps/api/migrations/versions/0011_requirements.py");

  assert.match(migration, /revision:\s*str\s*=\s*["']0011_requirements["']/);
  assert.match(migration, /context_version >= 1/);
  assert.match(
    migration,
    /functional','content','visual','technical','constraint','business/
  );
  assert.match(migration, /must','should','could/);
  assert.match(migration, /draft','confirmed','superseded','removed/);
  assert.match(migration, /created_by_type IN \('ai','user'\)/);
  assert.match(migration, /jsonb_typeof\(source_refs\) = 'array'/);
  assert.match(migration, /ondelete=["']RESTRICT["']/g);
  assert.doesNotMatch(
    migration,
    /context_version_id|acceptance_note|requirement_type|source_type/
  );
});

test("Requirement persistence enforces context and provenance boundaries", async () => {
  const domain = await read(
    "apps/api/app/modules/requirements/domain/requirement.py"
  );
  const application = await read(
    "apps/api/app/modules/requirements/application/requirement_service.py"
  );
  const repository = await read(
    "apps/api/app/modules/requirements/infrastructure/repository.py"
  );

  assert.doesNotMatch(domain, /fastapi|sqlalchemy|supabase|aria_observability/i);
  assert.doesNotMatch(application, /fastapi|sqlalchemy|supabase/i);
  assert.match(application, /requirement\.context_version > current_context_version/);
  assert.match(application, /resolve_provenance/);
  assert.match(repository, /ProjectModel\.deleted_at\.is_\(None\)/);
  assert.match(repository, /ContextSourceVersionModel\.parse_status == ["']ready["']/);
  assert.match(repository, /ContextSourceVersionModel\.account_id == account_id/);
  assert.match(repository, /ContextSourceVersionModel\.project_id == project_id/);
});

test("I01 keeps deferred Requirement behavior out of scope", async () => {
  const migration = await read("apps/api/migrations/versions/0011_requirements.py");
  const application = await read(
    "apps/api/app/modules/requirements/application/requirement_service.py"
  );
  const main = await read("apps/api/app/main.py");

  assert.doesNotMatch(migration, /unique.*requirement|acceptance_note/i);
  assert.doesNotMatch(application, /merge|dedup|generate|deactivate|restore/i);
  assert.doesNotMatch(main, /requirements.*router|create_requirements_router/i);
});

test("Requirement logging excludes customer content and provenance", async () => {
  const application = await read(
    "apps/api/app/modules/requirements/application/requirement_service.py"
  );
  const emitCall = application.slice(application.indexOf('"requirement.created"'));

  assert.match(emitCall, /requirement_id/);
  assert.match(emitCall, /context_version/);
  assert.match(emitCall, /priority/);
  assert.match(emitCall, /created_by_type/);
  assert.doesNotMatch(emitCall, /persisted\.(title|description|source_refs)/);
});
