import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Context Inbox keeps source and structured Context routes distinct", async () => {
  const sourcePage = await read("../src/app/projects/[projectId]/context/sources/page.tsx");
  const contextPage = await read("../src/app/projects/[projectId]/context/page.tsx");
  const navigation = await read("../src/features/context/context-navigation.tsx");
  assert.match(sourcePage, /ContextInbox/);
  assert.match(contextPage, /ContextReview/);
  assert.match(navigation, /زمینه ساختاریافته/);
  assert.match(navigation, /منابع/);
  assert.match(navigation, /context\/sources/);
});

test("Context Inbox exposes only paste text and fail-closed TXT upload", async () => {
  const inbox = await read("../src/features/context-sources/context-inbox.tsx");
  const page = await read("../src/app/projects/[projectId]/context/sources/page.tsx");
  const env = await read("../../../.env.example");
  assert.match(inbox, /چسباندن متن/);
  assert.match(inbox, /فایل TXT/);
  assert.doesNotMatch(inbox, /URL|یادداشت داخلی/);
  assert.match(page, /NEXT_PUBLIC_TXT_UPLOAD_ENABLED === "true"/);
  assert.match(env, /NEXT_PUBLIC_TXT_UPLOAD_ENABLED=false/);
});

test("Polling is bounded, visibility-aware and overlap-safe", async () => {
  const inbox = await read("../src/features/context-sources/context-inbox.tsx");
  assert.match(inbox, /5_000/);
  assert.match(inbox, /document\.hidden/);
  assert.match(inbox, /visibilitychange/);
  assert.match(inbox, /pollInFlightRef/);
  assert.match(inbox, /queued/);
  assert.match(inbox, /running/);
  assert.match(inbox, /تازه‌سازی/);
  assert.doesNotMatch(inbox, /progress.*%|درصد پیشرفت/i);
});

test("Archive and retry use only backend-owned capabilities", async () => {
  const inbox = await read("../src/features/context-sources/context-inbox.tsx");
  const types = await read("../src/features/context-sources/types.ts");
  assert.match(types, /can_archive: boolean/);
  assert.match(inbox, /source\.can_archive/);
  assert.match(inbox, /latest_job\.retryable/);
  assert.match(inbox, /window\.confirm/);
  assert.doesNotMatch(types, /created_by|storage_ref|object_key|signed_url|raw_text/);
});

test("Pagination is Load More and statuses use text plus SVG", async () => {
  const inbox = await read("../src/features/context-sources/context-inbox.tsx");
  assert.match(inbox, /نمایش منابع بیشتر/);
  assert.match(inbox, /<svg/);
  assert.match(inbox, /aria-label/);
});
