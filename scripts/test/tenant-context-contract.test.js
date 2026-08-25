import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("tenant dependency preserves the approved authentication and layering flow", async () => {
  const dependency = await read("apps/api/app/api/dependencies/tenant_context.py");
  const useCase = await read(
    "apps/api/app/modules/identity/application/tenant_context.py"
  );

  assert.match(dependency, /Depends\(ensure_bootstrapped_identity\)/);
  assert.match(dependency, /tenant_context_resolver\.execute/);
  assert.doesNotMatch(dependency, /sqlalchemy|AsyncSession|\bselect\s*\(/i);
  assert.doesNotMatch(useCase, /fastapi|sqlalchemy|supabase/i);
});

test("account context transport and stable errors match the owner-approved contract", async () => {
  const dependency = await read("apps/api/app/api/dependencies/tenant_context.py");
  const errors = await read("apps/api/app/api/errors.py");
  const openApi = await read("packages/contracts/openapi.yaml");

  assert.match(dependency, /request\.headers\.get\("X-Account-ID"\)/);
  assert.match(dependency, /tenant\.context_rejected/);
  assert.match(dependency, /tenant\.membership_denied/);
  assert.match(errors, /status_code=400/);
  assert.match(errors, /ACCOUNT_CONTEXT_REQUIRED/);
  assert.match(errors, /A valid account context is required\./);
  assert.match(openApi, /name: X-Account-ID/);
  assert.match(openApi, /format: uuid/);
  assert.match(openApi, /ACCOUNT_CONTEXT_REQUIRED/);
  assert.match(openApi, /MEMBERSHIP_REQUIRED/);
});

test("trace enrichment occurs only after active Membership authorization", async () => {
  const tenantDependency = await read(
    "apps/api/app/api/dependencies/tenant_context.py"
  );
  const bootstrapDependency = await read(
    "apps/api/app/api/dependencies/account_bootstrap.py"
  );

  const resolveIndex = tenantDependency.indexOf("tenant_context_resolver.execute");
  const enrichIndex = tenantDependency.lastIndexOf("enrich_trace_context");
  assert.ok(resolveIndex >= 0 && enrichIndex > resolveIndex);
  assert.doesNotMatch(bootstrapDependency, /enrich_trace_context/);
});

test("Tenant Context adds no schema or provider authority", async () => {
  const useCase = await read(
    "apps/api/app/modules/identity/application/tenant_context.py"
  );
  const migration = await read(
    "apps/api/migrations/versions/0001_identity_projection.py"
  );

  assert.match(useCase, /MembershipResolver/);
  assert.doesNotMatch(useCase, /JWT|claims|user_metadata|app_metadata/);
  assert.match(migration, /UniqueConstraint\(\s*"account_id", "user_id"/);
});
