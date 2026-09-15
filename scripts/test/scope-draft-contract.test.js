import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const migration = "apps/api/migrations/versions/0017_scope_drafts.py";
const domain = "apps/api/app/modules/scope/domain/scope_draft.py";
const model = "apps/api/app/modules/scope/infrastructure/models.py";
const adr = "docs/adr/ADR-041-scope-draft-model.md";

test("K01 has strict versioned content and all canonical sections", async () => {
  const source = await readFile(domain, "utf8");
  assert.match(source, /scope_content_schema_v1/);
  for (const section of ["summary", "goals", "pages_sections", "requirements", "content", "visual_direction", "constraints", "assumptions", "resolved_gaps", "remaining_non_blocking_gaps", "out_of_scope", "acceptance_notes"]) assert.match(source, new RegExp(`"${section}"`));
  assert.match(source, /Unknown schema version|Unknown Scope content schema version/);
});

test("K01 persistence is tenant-scoped and concurrency-ready", async () => {
  const source = `${await readFile(migration, "utf8")}\n${await readFile(model, "utf8")}`;
  assert.match(source, /UNIQUE|UniqueConstraint/);
  assert.match(source, /scope_draft_context_version/);
  assert.match(source, /scope_drafts_project_context_version/);
  assert.match(source, /updated_by_type/);
  assert.match(source, /ON DELETE|ondelete/);
});

test("K01 keeps readiness, revision and public API outside the increment", async () => {
  const source = await readFile(adr, "utf8");
  assert.match(source, /readiness/);
  assert.match(source, /revision/);
  assert.match(source, /public HTTP routes/);
});

test("K01 logs are content-safe by contract", async () => {
  const source = await readFile(adr, "utf8");
  assert.match(source, /never\s+contain\s+content/);
  assert.match(source, /scope_draft.version_conflict/);
});
