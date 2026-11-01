import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0088 accepts a body-only token on one unauthenticated POST route", async () => {
  const router = await read("apps/api/app/api/routers/public_scope_shares.py");
  assert.match(router, /prefix="\/public\/scope-shares"/);
  assert.match(router, /@router\.post\("\/resolve"/);
  assert.match(router, /ConfigDict\(extra="forbid"\)/);
  assert.doesNotMatch(router, /require_tenant_context|Authorization|X-Account-ID/);
  assert.doesNotMatch(router, /@router\.(get|put|patch|delete)/);
});

test("0088 validates canonical tokens before hash-only indexed resolution", async () => {
  const resolver = await read("apps/api/app/modules/sharing/application/public_resolver.py");
  const repository = await read("apps/api/app/modules/sharing/infrastructure/repository.py");
  assert.match(resolver, /urlsafe_b64decode/);
  assert.match(resolver, /len\(decoded\) != 32/);
  assert.match(resolver, /ScopeShareTokenHasher/);
  assert.match(repository, /ScopeShareLinkModel\.token_hash == token_hash/);
  assert.match(repository, /ScopeShareLinkModel\.revoked_at\.is_\(None\)/);
  assert.match(repository, /ScopeShareLinkModel\.expires_at > now/);
  assert.match(repository, /with_for_update\(read=True/);
  assert.doesNotMatch(repository, /latest|version_no\.desc/);
});

test("0088 exposes an independent minimal immutable-snapshot DTO", async () => {
  const router = await read("apps/api/app/api/routers/public_scope_shares.py");
  assert.match(router, /version_no: int/);
  assert.match(router, /snapshot_data: dict\[str, object\]/);
  for (const forbidden of [
    "account_id:",
    "project_id:",
    "created_by:",
    "token_hash:",
    "public_token:",
    "snapshot_hash:",
  ]) {
    assert.doesNotMatch(router, new RegExp(forbidden));
  }
});

test("0088 applies no-store to success and error responses without body logging", async () => {
  const middleware = await read("apps/api/app/api/middleware/public_share_no_store.py");
  const observability = await read("apps/api/app/api/middleware/observability.py");
  assert.match(middleware, /Cache-Control/);
  assert.match(middleware, /no-store/);
  assert.doesNotMatch(observability, /request_body|body=/);
});

test("0088 keeps direct Data API access denied", async () => {
  const migration = await read("apps/api/migrations/versions/0034_scope_share_links.py");
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /REVOKE ALL PRIVILEGES/);
  assert.doesNotMatch(migration, /CREATE POLICY/i);
});
