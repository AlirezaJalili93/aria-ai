import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const read = (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8")

test("0093 records the exact projections and secure fragment bootstrap decision", async () => {
  const [adr, development, report] = await Promise.all([
    read("docs/adr/ADR-080-scope-review-projections-and-browser-bootstrap.md"),
    read("docs/development/0093-scope-review-projections-browser-bootstrap/development.md"),
    read("docs/development/0093-scope-review-projections-browser-bootstrap/test-report.md")
  ])

  assert.match(adr, /Status:\*\* Accepted/)
  assert.match(adr, /\/scope-review#token=<raw-token>/)
  assert.match(adr, /history\.replaceState/)
  assert.match(adr, /volatile browser memory/)
  assert.match(development, /REQ-9301/)
  assert.match(development, /\*\*Unapproved assumptions:\*\* None/)
  assert.match(report, /TC-9301/)
})

test("OpenAPI exposes allowlisted authenticated projections and exact public decision status", async () => {
  const contract = await read("packages/contracts/openapi.yaml")

  assert.match(contract, /\/projects\/\{project_id\}\/scope\/versions\/\{version_no\}\/shares:/)
  assert.match(contract, /\/projects\/\{project_id\}\/scope\/versions\/\{version_no\}\/decision:/)
  assert.match(contract, /status: \{ type: string, enum: \[active, expired, revoked\] \}/)
  assert.match(contract, /decision_type: \{ type: string, const: change_request \}/)
  assert.match(contract, /decision_status:[\s\S]{0,160}awaiting_approval, approved, changes_requested, superseded/)
})

test("browser bootstrap removes the fragment before body-token resolution and persists nothing", async () => {
  const [parser, bootstrap, api, page] = await Promise.all([
    read("apps/web/src/features/scope-review/bootstrap.ts"),
    read("apps/web/src/features/scope-review/scope-review-bootstrap.tsx"),
    read("apps/web/src/features/scope-review/api.ts"),
    read("apps/web/src/app/scope-review/page.tsx")
  ])

  assert.match(parser, /history\.replaceState\(history\.state, "", "\/scope-review"\)/)
  assert.ok(bootstrap.indexOf("consumeScopeReviewToken") < bootstrap.indexOf("resolvePublicScope(tokenRef.current)"))
  assert.match(api, /publicRequest\("public\/scope-shares\/resolve", \{ token \}\)/)
  assert.match(api, /body: JSON\.stringify\(body\)/)
  assert.match(api, /cache: "no-store"/)
  assert.match(`${page}\n${bootstrap}`, /مرور محدوده پروژه/)
  assert.doesNotMatch(
    `${parser}\n${bootstrap}\n${api}`,
    /localStorage|sessionStorage|indexedDB|document\.cookie|emitProductEvent|console\./
  )
})
