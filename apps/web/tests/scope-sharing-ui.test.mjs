import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const read = (path) => readFile(new URL(path, import.meta.url), "utf8")

test("authenticated sharing is server-authorized and keeps raw token in client memory only", async () => {
  const [page, api, actions, settings] = await Promise.all([
    read("../src/app/projects/[projectId]/scope/versions/[versionNo]/share/page.tsx"),
    read("../src/features/scope-sharing/api.ts"),
    read("../src/features/scope-sharing/actions.ts"),
    read("../src/features/scope-sharing/scope-share-settings.tsx")
  ])
  assert.match(page, /resolveProjectAccess/)
  assert.match(api, /\/shares`/)
  assert.match(api, /\/decision`/)
  assert.match(actions, /"use server"/)
  assert.match(settings, /window\.location\.origin.*\/scope-review#token=/s)
  assert.match(settings, /navigator\.clipboard\.writeText\(shareUrl\)/)
  assert.match(settings, /createState\.tokenAvailable === false/)
  assert.doesNotMatch(`${page}\n${api}\n${actions}\n${settings}`, /localStorage|sessionStorage|indexedDB|document\.cookie|console\.|emitProductEvent/)
})

test("superseded versions cannot create new links and revoke remains explicit", async () => {
  const settings = await read("../src/features/scope-sharing/scope-share-settings.tsx")
  assert.match(settings, /version\.status === "superseded"/)
  assert.match(settings, /لینک جدید ساخته نمی‌شود/)
  assert.match(settings, /window\.confirm\("دسترسی این لینک لغو شود؟"\)/)
  assert.match(settings, /share\.canRevoke/)
})

test("guest forms expose labels, bounded fields, confirmation and pending guards", async () => {
  const review = await read("../src/features/scope-review/scope-review-bootstrap.tsx")
  assert.match(review, /htmlFor="guest-name"/)
  assert.match(review, /minLength=\{2\}/)
  assert.match(review, /maxLength=\{100\}/)
  assert.match(review, /maxLength=\{4000\}/)
  assert.match(review, /explicitly|صریحاً/u)
  assert.match(review, /window\.confirm/)
  assert.match(review, /disabled=\{pending\}/)
  assert.match(review, /role="alert"/)
})
