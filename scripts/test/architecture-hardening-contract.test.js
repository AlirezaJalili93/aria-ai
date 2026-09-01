import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("security hardening downgrade never restores broad Data API privileges", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0001a_identity_projection_access_hardening.py"
  );
  const downgrade = migration.split("def downgrade() -> None:")[1] ?? "";

  assert.doesNotMatch(downgrade, /\bGRANT\b/i);
  assert.match(downgrade, /DISABLE ROW LEVEL SECURITY/);
});

test("Bootstrap HTTP mapping handles only declared failure types", async () => {
  const dependency = await read("apps/api/app/api/dependencies/account_bootstrap.py");
  const useCase = await read(
    "apps/api/app/modules/identity/application/account_bootstrap.py"
  );

  assert.doesNotMatch(dependency, /except\s+Exception/);
  assert.match(dependency, /AccountBootstrapInfrastructureError/);
  assert.match(dependency, /AccountBootstrapInvariantError/);
  assert.match(useCase, /class AccountBootstrapInfrastructureError/);
});

test("Tenant Context authenticates and authorizes without implicit Bootstrap", async () => {
  const dependency = await read("apps/api/app/api/dependencies/tenant_context.py");

  assert.match(dependency, /Depends\(require_authenticated_identity\)/);
  assert.doesNotMatch(dependency, /ensure_bootstrapped_identity|AccountBootstrapContext/);
  assert.match(dependency, /tenant_context_resolver\.execute\(identity, account_id\)/);
});

test("Account discovery is a separate read-only pre-tenant contract", async () => {
  const decision = await read("docs/adr/ADR-011-pre-tenant-account-discovery.md");
  const bootstrapDecision = await read(
    "docs/adr/ADR-009-pre-tenant-account-bootstrap-command.md"
  );

  assert.match(decision, /GET \/api\/v1\/accounts/);
  assert.match(decision, /returns only active Memberships/i);
  assert.match(decision, /`id` and `role`/);
  assert.match(decision, /meta\.next_cursor` is `null`/);
  assert.match(decision, /meta\.has_more` is `false`/);
  assert.match(decision, /does not accept\s+`X-Account-ID`/);
  assert.match(decision, /performs no Bootstrap or mutation/i);
  assert.match(bootstrapDecision, /Return no Account, Profile, Membership/);
});
