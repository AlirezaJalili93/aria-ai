import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const read = (path) => readFile(new URL(path, import.meta.url), "utf8")

test("Scope review consumes only a fragment capability and clears it before resolution", async () => {
  const parser = await read("../src/features/scope-review/bootstrap.ts")
  const bootstrap = await read("../src/features/scope-review/scope-review-bootstrap.tsx")

  assert.match(parser, /location\.hash/)
  assert.match(parser, /parameters\.getAll\("token"\)/)
  assert.match(parser, /history\.replaceState\(history\.state, "", "\/scope-review"\)/)
  assert.ok(
    bootstrap.indexOf("consumeScopeReviewToken") < bootstrap.indexOf("resolvePublicScope(tokenRef.current)"),
    "the fragment must be consumed and replaced before the API request"
  )
  assert.doesNotMatch(`${parser}\n${bootstrap}`, /localStorage|sessionStorage|indexedDB|document\.cookie/)
  assert.doesNotMatch(bootstrap, /emitProductEvent|console\.|analytics|telemetry/)
})

test("Public Scope resolution sends the capability only in a no-store POST body", async () => {
  const api = await read("../src/features/scope-review/api.ts")

  assert.match(api, /publicRequest\("public\/scope-shares\/resolve", \{ token \}\)/)
  assert.match(api, /method: "POST"/)
  assert.match(api, /body: JSON\.stringify\(body\)/)
  assert.match(api, /cache: "no-store"/)
  assert.doesNotMatch(api, /console\.|localStorage|sessionStorage|document\.cookie/)
  assert.doesNotMatch(api, /\?token=|\/\$\{token\}/)
})

test("Guest review renders all sections and only terminal decision actions", async () => {
  const page = await read("../src/app/scope-review/page.tsx")
  const bootstrap = await read("../src/features/scope-review/scope-review-bootstrap.tsx")
  const combined = `${page}\n${bootstrap}`

  assert.match(combined, /مرور محدوده پروژه/)
  assert.match(page, /robots: \{ index: false, follow: false \}/)
  assert.match(bootstrap, /publicScopeSectionIds|scope\.snapshotData\.sections/)
  assert.match(bootstrap, /scope\.decisionStatus === "awaiting_approval"/)
  assert.match(bootstrap, /تأیید محدوده/)
  assert.match(bootstrap, /درخواست تغییر/)
  assert.doesNotMatch(combined, /project[_ -]?title|client[_ -]?title/iu)
})

test("Capability survives retryable failures and is cleared only after a confirmed terminal mutation", async () => {
  const bootstrap = await read("../src/features/scope-review/scope-review-bootstrap.tsx")

  assert.doesNotMatch(bootstrap, /\.finally\(\(\) => \{\s*tokenRef\.current = null/)
  assert.match(bootstrap, /await approvePublicScope[\s\S]{0,240}clearToken\(\)[\s\S]{0,120}onTerminal\("approved"\)/)
  assert.match(bootstrap, /await requestPublicScopeChanges[\s\S]{0,300}clearToken\(\)[\s\S]{0,120}onTerminal\("changes_requested"\)/)
  assert.match(bootstrap, /idempotencyKey: approvalKey\.current/)
  assert.match(bootstrap, /idempotencyKey: changeKey\.current/)
  assert.doesNotMatch(bootstrap, /localStorage|sessionStorage|indexedDB|document\.cookie|emitProductEvent|console\./)
})
