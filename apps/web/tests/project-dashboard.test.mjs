import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Account resolution blocks tenant requests unless exactly one account is active", async () => {
  const api = await read("../src/features/projects/api.ts");

  assert.match(api, /fetchAccounts\(accessToken\)/);
  assert.match(api, /accounts\.length === 0[\s\S]*status: "none"/);
  assert.match(api, /accounts\.length > 1[\s\S]*status: "multiple"/);
  assert.match(api, /status: "selected"[\s\S]*accessToken[\s\S]*account: accounts\[0\]/);
  assert.doesNotMatch(api, /X-Account-ID["']?\]\s*=.*fetchAccounts/);
});

test("Project dashboard implements empty, populated and incremental list states", async () => {
  const page = await read("../src/app/projects/page.tsx");
  const list = await read("../src/features/projects/project-list.tsx");
  const loading = await read("../src/app/projects/loading.tsx");
  const error = await read("../src/app/projects/error.tsx");
  const combined = `${page}\n${list}\n${loading}\n${error}`;

  assert.match(combined, /ایجاد اولین پروژه/);
  assert.match(combined, /initialProjects/);
  assert.match(combined, /loadMoreProjectsAction/);
  assert.match(combined, /new Set\(current\.map/);
  assert.match(combined, /نمایش پروژه‌های بیشتر/);
  assert.match(combined, /در حال بارگذاری پروژه‌ها/);
  assert.match(combined, /تلاش دوباره/);
});

test("Create form is one step, title/type only and retry-stable", async () => {
  const page = await read("../src/app/projects/new/page.tsx");
  const form = await read("../src/features/projects/create-project-form.tsx");
  const actions = await read("../src/features/projects/actions.ts");
  const combined = `${page}\n${form}\n${actions}`;

  assert.match(form, /name="title"/);
  assert.match(form, /name="project_type"/);
  assert.match(form, /landing/);
  assert.match(form, /corporate/);
  assert.match(form, /portfolio/);
  assert.match(form, /useFormStatus\(\)/);
  assert.match(form, /disabled=\{pending\}/);
  assert.match(actions, /previousState\.idempotencyKey/);
  assert.match(actions, /submissionFingerprint/);
  assert.match(actions, /redirect\(`\/projects\/\$\{projectId\}`\)/);
  assert.doesNotMatch(combined, /description|client_name|template|brief/i);
});

test("Overview renders only real metadata and explicit unavailable modules", async () => {
  const overview = await read("../src/app/projects/[projectId]/page.tsx");
  const overviewView = await read("../src/features/projects/project-overview.tsx");
  const notFound = await read("../src/app/projects/[projectId]/not-found.tsx");
  const combined = `${overview}\n${overviewView}\n${notFound}`;

  assert.match(overviewView, /project\.title/);
  assert.match(overviewView, /project\.project_type/);
  assert.match(overviewView, /project\.status/);
  assert.match(overviewView, /project\.updated_at/);
  assert.match(overviewView, /هنوز شروع نشده/);
  assert.match(overviewView, /Context/);
  assert.match(overviewView, /Requirements/);
  assert.match(overviewView, /Gaps/);
  assert.match(overviewView, /Scope/);
  assert.match(overview, /projectFailure\.status === 404[\s\S]*notFound\(\)/);
  assert.match(notFound, /پروژه در این فضای کاری در دسترس نیست/);
  assert.doesNotMatch(combined, /progress|readiness|percentage|percent|gap_count|requirement_count/i);
});

test("Product Analytics is versioned and excludes project content", async () => {
  const analytics = await read("../src/features/analytics/product-events.ts");
  const createForm = await read("../src/features/projects/create-project-form.tsx");
  const opened = await read("../src/features/projects/project-opened-event.tsx");
  const apiService = await read("../../api/app/modules/projects/application/project_service.py");
  const combined = `${analytics}\n${createForm}\n${opened}\n${apiService}`;

  for (const event of ["project_created", "project_opened", "project_type_selected"]) {
    assert.match(combined, new RegExp(event));
  }
  assert.match(analytics, /event_category: "product_analytics"/);
  assert.match(analytics, /schema_version: "1"/);
  for (const property of ["account_id", "project_id", "project_type", "role"]) {
    assert.match(analytics, new RegExp(property));
  }
  assert.doesNotMatch(analytics, /title|token|payload|content/i);
  assert.match(apiService, /project_created[\s\S]*event_category="product_analytics"/);
});

test("Dashboard UI stays RTL-tokenized, semantic and minimum-target compliant", async () => {
  const form = await read("../src/features/projects/create-project-form.tsx");
  const list = await read("../src/features/projects/project-list.tsx");
  const styles = await read("../src/app/globals.css");
  const combined = `${form}\n${list}`;

  assert.match(combined, /<label/);
  assert.match(combined, /<fieldset/);
  assert.match(combined, /aria-live="polite"|role="alert"/);
  assert.match(styles, /min-block-size:\s*var\(--button-height\)/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.match(styles, /@media \(min-width: 48rem\)/);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
});
