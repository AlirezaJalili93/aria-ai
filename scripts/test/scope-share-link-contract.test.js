import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0087 issues a 32-byte unpadded Base64URL token and persists only its SHA-256 hash", async () => {
  const tokens = await read("apps/api/app/modules/sharing/infrastructure/tokens.py");
  const model = await read("apps/api/app/modules/sharing/infrastructure/models.py");
  assert.match(tokens, /token_bytes\(32\)/);
  assert.match(tokens, /urlsafe_b64encode/);
  assert.match(tokens, /rstrip\(b"="\)/);
  assert.match(tokens, /sha256\(public_token\.encode\("utf-8"\)\)/);
  assert.match(model, /token_hash/);
  assert.doesNotMatch(model, /raw_token|public_token/);
});

test("0087 migration enforces exact tenant/version binding and terminal lifecycle", async () => {
  const migration = await read("apps/api/migrations/versions/0034_scope_share_links.py");
  assert.match(migration, /scope_version_id.*account_id.*project_id/s);
  assert.match(migration, /scope_versions\.id.*scope_versions\.account_id.*scope_versions\.project_id/s);
  assert.match(migration, /octet_length\(token_hash\) = 32/);
  assert.match(migration, /expires_at > created_at/);
  assert.match(migration, /scope share links cannot be deleted/);
  assert.match(migration, /revocation is terminal/);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /REVOKE ALL PRIVILEGES/);
});

test("0087 authorization is application-owned and tenant-scoped", async () => {
  const service = await read("apps/api/app/modules/sharing/application/service.py");
  const repository = await read("apps/api/app/modules/sharing/infrastructure/repository.py");
  assert.match(service, /membership_status != "active"/);
  assert.match(service, /context\.role not in \{"owner", "admin"\}/);
  assert.match(service, /link\.created_by != context\.subject_id/);
  assert.match(repository, /ScopeVersionModel\.account_id == account_id/);
  assert.match(repository, /ScopeVersionModel\.project_id == project_id/);
  assert.match(repository, /ScopeShareLinkModel\.account_id == account_id/);
  assert.match(repository, /ScopeShareLinkModel\.project_id == project_id/);
});

test("0087 never logs tokens, hashes or Scope content", async () => {
  const service = await read("apps/api/app/modules/sharing/application/service.py");
  for (const event of [
    "scope_share_link.created",
    "scope_share_link.revoked",
    "scope_share_link.revoke_replayed",
    "scope_share_link.persistence_failed",
  ]) {
    assert.match(service, new RegExp(event.replaceAll(".", "\\.")));
  }
  const emitBlocks = [...service.matchAll(/self\._event_logger\.emit\(([\s\S]*?)\n\s*\)/g)].map(
    (match) => match[1],
  );
  assert.ok(emitBlocks.length >= 3);
  for (const block of emitBlocks) {
    assert.doesNotMatch(block, /public_token=|token_hash=|snapshot_data=|content=/);
  }
});

test("0087 foundation remains transport-free after 0088 composes public resolution", async () => {
  const service = await read("apps/api/app/modules/sharing/application/service.py");
  const decision = await read("docs/adr/ADR-075-public-scope-share-resolution.md");
  assert.doesNotMatch(service, /fastapi|APIRouter|@router/i);
  assert.match(decision, /Status:\*\* Accepted/);
  assert.match(decision, /POST \/api\/v1\/public\/scope-shares\/resolve/);
});
