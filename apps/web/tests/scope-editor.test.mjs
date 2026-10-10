import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Scope route is tenant-authorized, current-only and linked from Project Overview", async () => {
  const page = await read("../src/app/projects/[projectId]/scope/page.tsx");
  const overview = await read("../src/features/projects/project-overview.tsx");
  const api = await read("../src/features/scope/api.ts");

  assert.match(page, /resolveProjectAccess\(\)/);
  assert.match(page, /access\.status === "auth_required"[\s\S]*redirect\("\/auth\/login"\)/);
  assert.match(page, /error\.status === 404/);
  assert.match(api, /projects\/\$\{encodeURIComponent\(projectId\)\}\/scope\/draft/);
  assert.match(overview, /href=\{`\/projects\/\$\{project\.id\}\/scope`\}/);
});

test("Scope mutation is one-section CAS and never sends trace", async () => {
  const api = await read("../src/features/scope/api.ts");
  const actions = await read("../src/features/scope/actions.ts");

  assert.match(api, /scope\/draft\/sections\/\$\{sectionId\}/);
  assert.match(api, /\{ value, expected_updated_at: expectedUpdatedAt \}/);
  assert.match(actions, /expected_updated_at/);
  assert.match(actions, /VERSION_CONFLICT/);
  assert.match(actions, /SCOPE_DRAFT_STALE/);
  assert.doesNotMatch(`${api}\n${actions}`, /body:[\s\S]{0,180}trace/);
});

test("Scope editor covers twelve sections, explicit save and unsaved protection", async () => {
  const editor = await read("../src/features/scope/scope-editor.tsx");
  const types = await read("../src/features/scope/types.ts");
  const actions = await read("../src/features/scope/actions.ts");

  for (const section of ["summary", "goals", "pages_sections", "requirements", "content", "visual_direction", "constraints", "assumptions", "resolved_gaps", "remaining_non_blocking_gaps", "out_of_scope", "acceptance_notes"]) {
    assert.match(types, new RegExp(`\\"${section}\\"`));
  }
  assert.match(editor, /ذخیره بخش/);
  assert.match(editor, /beforeunload/);
  assert.match(editor, /window\.confirm/);
  assert.match(actions, /تغییرات شما حفظ شده/);
  assert.match(editor, /منشأ اولیه تولید بخش/);
});

test("Scope UI has no regeneration or fabricated progress and analytics stays content-free", async () => {
  const editor = await read("../src/features/scope/scope-editor.tsx");
  const analytics = await read("../src/features/analytics/product-events.ts");
  const styles = await read("../src/app/globals.css");
  const combined = `${editor}\n${analytics}`;

  assert.doesNotMatch(combined, /regenerat|باز.?تولید|coming soon|به.?زودی|readiness.?%|completion.?%|AI score/iu);
  assert.match(analytics, /scope_edited/);
  assert.match(analytics, /section_id/);
  assert.match(analytics, /context_version/);
  assert.doesNotMatch(analytics, /scope_value|scope_content|trace|customer_content/iu);
  assert.match(styles, /min-block-size: var\(--button-height\)/);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
});
