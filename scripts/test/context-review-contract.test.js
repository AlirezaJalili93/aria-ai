import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("H04 publishes current-version Context review contracts", async () => {
  const openapi = await read("packages/contracts/openapi.yaml");

  assert.match(openapi, /\/projects\/\{project_id\}\/context-items:/);
  assert.match(openapi, /item_type[\s\S]*status[\s\S]*source_id/);
  assert.match(openapi, /created_at DESC, id DESC/);
  assert.match(openapi, /default: 20/);
  assert.match(openapi, /maximum: 100/);
  assert.match(openapi, /command: \{ type: string, const: confirm \}/);
  assert.match(openapi, /command: \{ type: string, const: reject \}/);
  assert.match(openapi, /command: \{ type: string, const: edit \}/);
  assert.match(openapi, /expected_updated_at/);
  assert.match(openapi, /INVALID_CONTEXT_ITEM_STATE/);
  assert.match(openapi, /VERSION_CONFLICT/);
});

test("H04 keeps provenance visible and immutable during edit", async () => {
  const openapi = await read("packages/contracts/openapi.yaml");

  assert.match(openapi, /source_refs/);
  assert.match(openapi, /does not claim semantic re-validation/);
  assert.doesNotMatch(openapi, /command: \{ type: string, const: (delete|regenerate) \}/);
  assert.doesNotMatch(openapi, /updated_source_refs|replacement_source_refs/);
});

test("H04 schema extends Context Items with database-owned updated_at", async () => {
  const migration = await read("apps/api/migrations/versions/0010_context_item_review.py");
  const model = await read("apps/api/app/modules/context/infrastructure/models.py");

  assert.match(migration, /op\.add_column\([\s\S]*["']context_items["'][\s\S]*updated_at/);
  assert.match(migration, /trg_context_items_set_updated_at/);
  assert.match(migration, /ix_context_items_current_page/);
  assert.match(migration, /ix_context_items_source_refs_gin/);
  assert.match(model, /updated_at/);
});

test("H04 UI uses canonical item types and defers unapproved actions", async () => {
  const page = await read("apps/web/src/app/projects/[projectId]/context/page.tsx");
  const review = await read("apps/web/src/features/context/context-review.tsx");
  const actions = await read("apps/web/src/features/context/actions.ts");
  const combined = `${page}\n${review}\n${actions}`;

  for (const type of ["fact", "assumption", "decision", "constraint", "reference", "unknown"]) {
    assert.match(combined, new RegExp(type));
  }
  assert.match(combined, /اطلاعات ناقص/);
  assert.match(combined, /confirmContextItemAction/);
  assert.match(combined, /rejectContextItemAction/);
  assert.match(combined, /editContextItemAction/);
  assert.doesNotMatch(combined, /deleteContextItem|regenerateContextItem|context-structuring/);
});
