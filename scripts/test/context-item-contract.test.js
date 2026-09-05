import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("logical M004 implements the canonical Context Item schema", async () => {
  const migration = await read("apps/api/migrations/versions/0008_context_items.py");

  assert.match(migration, /revision:\s*str\s*=\s*["']0008_context_items["']/);
  assert.match(migration, /context_version >= 1/);
  assert.match(migration, /fact','assumption','decision','constraint','reference','unknown/);
  assert.match(migration, /proposed','confirmed','rejected','superseded/);
  assert.match(migration, /ai','user','system/);
  assert.match(migration, /jsonb_typeof\(source_refs\) = 'array'/);
  assert.match(migration, /jsonb_array_length\(source_refs\) > 0/);
  assert.match(migration, /ondelete=["']RESTRICT["']/g);
  assert.doesNotMatch(migration, /context_version_id|source_ref[^s]|state[^a-z]/);
});

test("Context Item persistence validates semantic provenance", async () => {
  const domain = await read("apps/api/app/modules/context/domain/context_item.py");
  const application = await read(
    "apps/api/app/modules/context/application/context_item_service.py"
  );
  const repository = await read(
    "apps/api/app/modules/context/infrastructure/context_item_repository.py"
  );

  assert.doesNotMatch(domain, /fastapi|sqlalchemy|supabase|aria_observability/i);
  assert.doesNotMatch(application, /fastapi|sqlalchemy|supabase|aria_observability/i);
  assert.match(application, /resolve_provenance/);
  assert.match(application, /canonical_text_length/);
  assert.match(repository, /ContextSourceVersionModel\.parse_status == ["']ready["']/);
  assert.match(repository, /ContextSourceVersionModel\.source_id == source_id/);
  assert.match(repository, /ContextSourceVersionModel\.account_id == account_id/);
  assert.match(repository, /ContextSourceVersionModel\.project_id == project_id/);
});

test("Context Item contract does not add deferred product surfaces", async () => {
  const migration = await read("apps/api/migrations/versions/0008_context_items.py");
  const service = await read(
    "apps/api/app/modules/context/application/context_item_service.py"
  );
  const main = await read("apps/api/app/main.py");

  assert.doesNotMatch(migration, /CREATE TABLE context_versions|create_table\(["']context_versions/);
  assert.doesNotMatch(service, /normalize|maximum|max_length|provider|prompt/i);
  assert.doesNotMatch(main, /context-items|context_items/);
});
