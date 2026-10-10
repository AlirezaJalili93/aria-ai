import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0092 persists complete immutable lineage and single-use Change Requests", async () => {
  const migration = await read("apps/api/migrations/versions/0037_scope_revision_lineage.py");
  const model = await read("apps/api/app/modules/scope/infrastructure/models.py");
  for (const source of [migration, model]) {
    assert.match(source, /revision_of_scope_version_id/);
    assert.match(source, /change_request_id/);
    assert.match(source, /scope_version_revision_lineage_pair/);
    assert.match(source, /uq_scope_versions_change_request/);
    assert.match(source, /RESTRICT/);
  }
  assert.match(migration, /NEW\.revision_of_scope_version_id IS DISTINCT FROM OLD/);
  assert.match(migration, /NEW\.change_request_id IS DISTINCT FROM OLD/);
});

test("0092 locks exact state and finalizes N plus N+1 atomically", async () => {
  const repository = await read(
    "apps/api/app/modules/scope/infrastructure/revision_repository.py",
  );
  const service = await read("apps/api/app/modules/scope/application/scope_revision_service.py");
  assert.match(repository, /ProjectModel[\s\S]*with_for_update/);
  assert.match(repository, /order_by\(ScopeVersionModel\.version_no\.desc\(\)\)/);
  assert.match(repository, /ScopeChangeRequestModel[\s\S]*with_for_update/);
  assert.match(repository, /ScopeDraftModel[\s\S]*with_for_update/);
  assert.match(service, /add_revision\(revision\)/);
  assert.match(service, /supersede_target/);
  assert.match(service, /complete_revision_reservation/);
  assert.match(service, /await unit_of_work\.commit\(\)/);
});

test("0092 exact replay precedes stale checks and K05 cannot bypass lineage", async () => {
  const revision = await read("apps/api/app/modules/scope/application/scope_revision_service.py");
  const freeze = await read("apps/api/app/modules/scope/application/scope_version_service.py");
  const replay = revision.indexOf("if not reservation.acquired");
  const stale = revision.indexOf("target.latest_scope_version_id");
  assert.ok(replay >= 0 && stale > replay);
  assert.match(freeze, /latest_status == "changes_requested"/);
  assert.match(freeze, /ScopeRevisionRequired/);
});

test("0092 exposes only the authenticated explicit command and safe metadata", async () => {
  const openapi = await read("packages/contracts/openapi.yaml");
  const router = await read("apps/api/app/api/routers/scope_versions.py");
  assert.match(openapi, /createScopeRevision/);
  assert.match(openapi, /change_request_id/);
  assert.match(openapi, /expected_draft_updated_at/);
  assert.match(openapi, /SCOPE_REVISION_STALE/);
  assert.match(openapi, /SCOPE_REVISION_REQUIRED/);
  assert.match(router, /\/{version_no}\/revisions/);
  assert.match(router, /result\.replayed/);
  assert.doesNotMatch(router, /comment|change_request\.comment/);
});

test("0092 telemetry excludes Draft, snapshot and Change Request content", async () => {
  const service = await read("apps/api/app/modules/scope/application/scope_revision_service.py");
  for (const event of [
    "scope_revision.created",
    "scope_revision.version_conflict",
    "scope_revision.creation_failed",
  ]) {
    assert.match(service, new RegExp(event.replaceAll(".", "\\.")));
  }
  const emitBlocks = [...service.matchAll(/self\._event_logger\.emit\(([\s\S]*?)\n\s*\)/g)].map(
    (match) => match[1],
  );
  for (const block of emitBlocks) {
    assert.doesNotMatch(block, /snapshot_data=|snapshot_hash=|draft=|comment=|change_request=/);
  }
});
