import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("K05 freezes the exact validated current Scope with versioned canonical hashing", async () => {
  const domain = await read("apps/api/app/modules/scope/domain/scope_version.py");
  const service = await read("apps/api/app/modules/scope/application/scope_version_service.py");
  assert.match(domain, /scope_snapshot_canonicalization_v1/);
  assert.match(domain, /sha256:/);
  assert.match(domain, /sort_keys=True/);
  assert.match(domain, /ensure_ascii=False/);
  assert.match(service, /expected_draft_updated_at/);
  assert.match(service, /ScopeReadinessPolicy/);
  assert.match(service, /deepcopy\(draft\.content\)/);
});

test("K05 evaluates idempotency before semantic duplicate rejection", async () => {
  const service = await read("apps/api/app/modules/scope/application/scope_version_service.py");
  const replay = service.indexOf("if not reservation.acquired");
  const duplicate = service.indexOf("target.latest_snapshot_hash");
  assert.ok(replay >= 0 && duplicate > replay);
  assert.match(service, /ScopeVersionIdempotencyConflict/);
  assert.match(service, /ScopeVersionUnchanged/);
});

test("K05 migration protects payload and keeps lifecycle status separately controlled", async () => {
  const migration = await read("apps/api/migrations/versions/0018_scope_versions.py");
  assert.match(migration, /UNIQUE|UniqueConstraint/);
  assert.match(migration, /protect_scope_version_snapshot/);
  assert.match(migration, /snapshot_data IS DISTINCT FROM OLD\.snapshot_data/);
  assert.doesNotMatch(migration, /NEW\.status IS DISTINCT FROM OLD\.status/);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /REVOKE ALL PRIVILEGES/);
});

test("K05 API exposes summary and detail reads but no mutation route", async () => {
  const openapi = await read("packages/contracts/openapi.yaml");
  const router = await read("apps/api/app/api/routers/scope_versions.py");
  assert.match(openapi, /createScopeVersion/);
  assert.match(openapi, /listScopeVersions/);
  assert.match(openapi, /getScopeVersion/);
  assert.match(openapi, /SCOPE_VERSION_UNCHANGED/);
  assert.match(router, /snapshot_data=version\.snapshot_data/);
  assert.doesNotMatch(router, /@router\.(patch|delete)/);
});

test("K05 operational events never emit snapshot payload or hash", async () => {
  const service = await read("apps/api/app/modules/scope/application/scope_version_service.py");
  for (const event of [
    "scope_version.created",
    "scope_version.unchanged_rejected",
    "scope_version.version_conflict",
    "scope_version.creation_failed",
  ]) {
    assert.match(service, new RegExp(event.replaceAll(".", "\\.")));
  }
  const emitBlocks = [...service.matchAll(/self\._event_logger\.emit\(([\s\S]*?)\n\s*\)/g)].map(
    (match) => match[1],
  );
  assert.ok(emitBlocks.length >= 4);
  for (const block of emitBlocks) {
    assert.doesNotMatch(block, /snapshot_data=|snapshot_hash=|trace=/);
  }
});
