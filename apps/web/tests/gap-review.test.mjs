import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Gap Inbox route is tenant-authorized and linked from Project Overview", async () => {
  const page = await read("../src/app/projects/[projectId]/gaps/page.tsx");
  const overview = await read("../src/features/projects/project-overview.tsx");
  assert.match(page, /resolveProjectAccess\(\)/);
  assert.match(page, /error\.status === 404[\s\S]*notFound\(\)/);
  assert.match(overview, /href=\{`\/projects\/\$\{project\.id\}\/gaps`\}/);
});

test("Gap Inbox covers filters, empty states, retry and pagination", async () => {
  const review = await read("../src/features/gaps/gap-review.tsx");
  for (const value of ["status", "severity", "gap_type", "meta.next_cursor", "meta.has_more", "تلاش دوباره", "پاک کردن فیلترها"]) assert.match(review, new RegExp(value.replace(".", "\\.")));
  assert.match(review, /aria-live="polite"/);
  assert.match(review, /aria-busy=\{pending\}/);
});

test("Severity is conveyed by visible text and one SVG icon family", async () => {
  const review = await read("../src/features/gaps/gap-review.tsx");
  const styles = await read("../src/app/globals.css");
  for (const label of ["بحرانی", "زیاد", "متوسط", "کم"]) assert.match(review, new RegExp(label));
  assert.match(review, /<svg aria-hidden="true"/);
  assert.match(styles, /severity-badge/);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
});

test("Human actions are distinct and terminal states remain read-only", async () => {
  const review = await read("../src/features/gaps/gap-review.tsx");
  assert.match(review, /provided_information/);
  assert.match(review, /internal_decision/);
  assert.match(review, /accepted_assumption/);
  assert.match(review, /ignored/);
  assert.match(review, /gap\.status === "open"/);
  assert.match(review, /item\.status === "open"/);
  assert.match(review, /gap\.gap_type === "unsupported_assumption" && gap\.suggested_resolution_type === "validate_assumption"/);
  assert.match(review, /window\.confirm/);
});

test("Gap UI contains no deferred generation, scoring, or severity mutation", async () => {
  const review = await read("../src/features/gaps/gap-review.tsx");
  assert.doesNotMatch(review, /recompute|generateQuestion|readiness.?score|confidence.?score|updateSeverity/i);
});
