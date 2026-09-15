import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("safe-not-found logging is bounded and performs no existence probe", async () => {
  const errors = await read("apps/api/app/api/errors.py");
  const handler = errors.slice(
    errors.indexOf("async def resource_not_found_handler"),
    errors.indexOf("async def idempotency_conflict_handler")
  );

  assert.match(handler, /resource\.access_denied/);
  assert.match(handler, /not_visible_in_tenant_scope/);
  assert.match(handler, /RESOURCE_NOT_FOUND/);
  assert.match(handler, /with suppress\(Exception\)/);
  assert.doesNotMatch(handler, /SELECT|select\(|repository|actual_owner|other_tenant/i);
});

test("security suite covers the canonical Tenant A and Tenant B attack matrix", async () => {
  const suite = await read("apps/api/tests/test_cross_tenant_security.py");

  for (const marker of [
    "account_selector_tampering",
    "context_item_b",
    "requirement_b",
    "gap_b",
    "scope_draft_b",
    "scope_version_b",
    "job_b",
    "RESOURCE_NOT_FOUND",
    "SET LOCAL ROLE authenticated",
  ]) {
    assert.match(suite, new RegExp(marker));
  }
});

test("no security-only endpoint or out-of-tenant owner field is introduced", async () => {
  const main = await read("apps/api/app/main.py");
  const logger = await read("packages/observability/src/aria_observability/logging.py");
  const openapi = await read("packages/contracts/openapi.yaml");

  assert.doesNotMatch(main, /security.*router|debug.*router/i);
  assert.doesNotMatch(openapi, /actual_owner_account_id|cross_tenant_account_id/);
  assert.doesNotMatch(logger, /actual_owner_account_id|cross_tenant_account_id/);
});
