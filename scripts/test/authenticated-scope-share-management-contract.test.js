import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0089 exposes authenticated create and revoke routes with mandatory idempotency", async () => {
  const router = await read("apps/api/app/api/routers/scope_shares.py");
  assert.match(router, /scope\/versions\/\{version_no\}\/share/);
  assert.match(router, /scope-shares\/\{share_link_id\}\/revoke/);
  assert.match(router, /Header\(alias="Idempotency-Key"\)/);
  assert.match(router, /Depends\(require_tenant_context\)/);
  assert.match(router, /status\.HTTP_201_CREATED/);
  assert.match(router, /status\.HTTP_204_NO_CONTENT/);
});

test("0089 persists only safe replay state and never the one-time token", async () => {
  const service = await read("apps/api/app/modules/sharing/application/service.py");
  assert.match(service, /token_available=False/);
  assert.match(service, /replayed=True/);
  assert.match(service, /response_ref=\{"scope_share_link_id": str\(link\.id\)\}/);
  assert.doesNotMatch(service, /response_ref=.*public_token|response_ref=.*token_hash/);
});

test("0089 binds idempotency at project-operation scope so a changed target conflicts", async () => {
  const service = await read("apps/api/app/modules/sharing/application/service.py");
  const repository = await read("apps/api/app/modules/sharing/infrastructure/repository.py");
  assert.match(service, /ScopeShareLinkIdempotencyConflict/);
  assert.match(service, /request_hash/);
  assert.match(repository, /POST:\/api\/v1\/projects\/\{project_id\}\/scope\/versions\/share/);
  assert.match(repository, /POST:\/api\/v1\/projects\/\{project_id\}\/scope-shares\/revoke/);
});

test("0089 documents the deliberate lost-response recovery and exclusions", async () => {
  const adr = await read("docs/adr/ADR-076-authenticated-scope-share-management-api.md");
  assert.match(adr, /Status:\*\* Accepted/);
  assert.match(adr, /token_available=false/);
  assert.match(adr, /revoke.*new Idempotency-Key/is);
  assert.match(adr, /Share URL construction.*deferred/is);
  assert.match(adr, /Unapproved assumptions:\*\* None/);
});
