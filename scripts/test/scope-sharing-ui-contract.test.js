import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import test from "node:test"

const read = (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8")

test("0094 records the frozen Share and Guest UI boundary", async () => {
  const [adr, development, report] = await Promise.all([
    read("docs/adr/ADR-081-scope-sharing-and-guest-decision-ui.md"),
    read("docs/development/0094-scope-sharing-guest-decision-ui/development.md"),
    read("docs/development/0094-scope-sharing-guest-decision-ui/test-report.md")
  ])
  assert.match(adr, /Status:\*\* Accepted/)
  assert.match(adr, /volatile memory/)
  assert.match(adr, /superseded ScopeVersion/)
  assert.match(development, /REQ-9401/)
  assert.match(development, /\*\*Unapproved assumptions:\*\* None/)
  assert.match(report, /TC-9401/)
})

test("public DTO and Web adapters prohibit internal lineage and persistent capability storage", async () => {
  const [contract, resolver, reviewApi, reviewUi, settings] = await Promise.all([
    read("packages/contracts/openapi.yaml"),
    read("apps/api/app/modules/sharing/application/public_resolver.py"),
    read("apps/web/src/features/scope-review/api.ts"),
    read("apps/web/src/features/scope-review/scope-review-bootstrap.tsx"),
    read("apps/web/src/features/scope-sharing/scope-share-settings.tsx")
  ])
  assert.match(contract, /PublicScopeSection:[\s\S]{0,180}required: \[section_id, value\]/)
  assert.match(resolver, /project_public_scope_content/)
  assert.match(resolver, /"sections": \[\{"name": item\["name"\]\}/)
  assert.doesNotMatch(reviewApi, /trace|context_item_ids|requirement_ids|gap_ids|item_id|version_hash/)
  assert.doesNotMatch(`${reviewApi}\n${reviewUi}\n${settings}`, /localStorage|sessionStorage|indexedDB|document\.cookie|console\.|emitProductEvent/)
  assert.match(reviewUi, /clearToken\(\)[\s\S]{0,120}onTerminal/)
  assert.doesNotMatch(reviewUi, /\.finally\(\(\) => \{\s*tokenRef\.current = null/)
})

test("new Share creation is server-rejected for superseded versions", async () => {
  const [service, repository, settings] = await Promise.all([
    read("apps/api/app/modules/sharing/application/service.py"),
    read("apps/api/app/modules/sharing/infrastructure/repository.py"),
    read("apps/web/src/features/scope-sharing/scope-share-settings.tsx")
  ])
  assert.match(service, /target\.status == "superseded"/)
  assert.match(repository, /lock_scope_version_for_share_create/)
  assert.match(repository, /with_for_update\(\)/)
  assert.match(settings, /version\.status === "superseded"/)
})
