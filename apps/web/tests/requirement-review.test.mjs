import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Requirement route is tenant-authorized and linked from the project overview", async () => {
  const page = await read("../src/app/projects/[projectId]/requirements/page.tsx");
  const overview = await read("../src/features/projects/project-overview.tsx");

  assert.match(page, /resolveProjectAccess\(\)/);
  assert.match(page, /access\.status === "auth_required"[\s\S]*redirect\("\/auth\/login"\)/);
  assert.match(page, /error\.status === 404[\s\S]*notFound\(\)/);
  assert.match(overview, /href=\{`\/projects\/\$\{project\.id\}\/requirements`\}/);
});

test("Requirement API adapter preserves filters, idempotency and optimistic concurrency", async () => {
  const api = await read("../src/features/requirements/api.ts");
  const actions = await read("../src/features/requirements/actions.ts");
  const combined = `${api}\n${actions}`;

  assert.match(api, /search\.set\("category", options\.category\)/);
  assert.match(api, /search\.set\("status", options\.status\)/);
  assert.match(api, /search\.set\("cursor", options\.cursor\)/);
  assert.match(api, /headers\["Idempotency-Key"\] = options\.idempotencyKey/);
  assert.match(actions, /submissionFingerprint/);
  assert.match(actions, /expected_updated_at: fields\.expectedUpdatedAt/);
  assert.match(api, /method: "DELETE"/);
  assert.match(combined, /VERSION_CONFLICT/);
  assert.match(combined, /INVALID_REQUIREMENT_STATE/);
});

test("Requirement response validation fails closed for provenance and confidence", async () => {
  const api = await read("../src/features/requirements/api.ts");

  assert.match(api, /value\.confidence < 0/);
  assert.match(api, /value\.confidence > 1/);
  assert.match(api, /hasStart !== hasEnd/);
  assert.match(api, /\(start as number\) < 0/);
  assert.match(api, /\(end as number\) <= \(start as number\)/);
  assert.match(api, /throw invalidResponse\(\)/);
});

test("Requirement review exposes canonical categories, states and source trace", async () => {
  const review = await read("../src/features/requirements/requirement-review.tsx");

  for (const category of ["functional", "content", "visual", "technical", "constraint", "business"]) {
    assert.match(review, new RegExp(`value: \\"${category}\\"`));
  }
  for (const status of ["draft", "confirmed", "superseded", "removed"]) {
    assert.match(review, new RegExp(`${status}:`));
  }
  assert.match(review, /source_refs\.length/);
  assert.match(review, /source_id/);
  assert.match(review, /source_version_id/);
  assert.match(review, /is_unsupported/);
  assert.match(review, /پیشنهاد هوش مصنوعی/);
});

test("Requirement mutations retain human control and protect unsaved edits", async () => {
  const review = await read("../src/features/requirements/requirement-review.tsx");
  const actions = await read("../src/features/requirements/actions.ts");
  const combined = `${review}\n${actions}`;

  assert.match(review, /item\.status === "draft"[\s\S]*confirmAction/);
  assert.match(review, /item\.status === "draft"[\s\S]*removeAction/);
  assert.match(review, /window\.confirm\("این نیازمندی غیرفعال شود؟"\)/);
  assert.match(review, /beforeunload/);
  assert.match(review, /تغییرات ذخیره‌نشده/);
  assert.match(review, /وضعیت این نیازمندی را به پیش‌نویس برمی‌گرداند/);
  assert.match(actions, /status: "confirmed"/);
  assert.doesNotMatch(combined, /hard.?delete|regenerateRequirement|generateRequirements/iu);
});

test("Requirement UI is tokenized, accessible and logs only safe analytics properties", async () => {
  const review = await read("../src/features/requirements/requirement-review.tsx");
  const analytics = await read("../src/features/analytics/product-events.ts");
  const styles = await read("../src/app/globals.css");

  assert.match(review, /aria-busy=\{isPending\}/);
  assert.match(review, /aria-live="polite"/);
  assert.match(review, /role="alert"/);
  assert.match(review, /<label/);
  assert.match(styles, /summary:focus-visible/);
  assert.match(styles, /textarea:focus-visible/);
  assert.match(styles, /select:focus-visible/);
  assert.match(styles, /min-block-size: var\(--button-height\)/);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
  assert.match(analytics, /requirement_edited/);
  assert.match(analytics, /requirement_removed/);
  assert.match(analytics, /requirement_id/);
  assert.doesNotMatch(analytics, /title|description|source_refs|acceptance_note|token|payload/i);
});

test("Requirement mutation analytics suppress duplicate client emission", async () => {
  const review = await read("../src/features/requirements/requirement-review.tsx");
  const actions = await read("../src/features/requirements/actions.ts");

  assert.match(actions, /eventId: randomUUID\(\)/);
  assert.match(review, /handledEvents\.current\.has\(state\.event\.eventId\)/);
  assert.match(review, /handledEvents\.current\.add\(state\.event\.eventId\)/);
});
