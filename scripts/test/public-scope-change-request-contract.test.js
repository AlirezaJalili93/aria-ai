import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0091 exposes body-token public Change Request with bounded canonical comment", async () => {
  const router = await read("apps/api/app/api/routers/public_scope_shares.py");
  const domain = await read(
    "apps/api/app/modules/sharing/domain/scope_change_request.py"
  );
  assert.match(router, /@router\.post\([\s\S]*"\/request-changes"/);
  assert.match(router, /Header\(alias="Idempotency-Key"\)/);
  assert.doesNotMatch(router, /request-changes.*\{token\}/);
  assert.match(domain, /replace\("\\r\\n", "\\n"\)\.replace\("\\r", "\\n"\)/);
  assert.match(domain, /1 <= len\(normalized\) <= 4000/);
});

test("0091 persists an independent immutable exact-version Change Request", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0036_scope_change_requests.py"
  );
  assert.match(migration, /create_table\(\s*"scope_change_requests"/);
  assert.match(migration, /version_hash/);
  assert.match(migration, /UniqueConstraint\(\s*"scope_version_id"/);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /BEFORE UPDATE OR DELETE/);
  assert.doesNotMatch(migration, /approval_type/);
});

test("0091 serializes Approval and Change Request on one terminal Scope Version", async () => {
  const approval = await read(
    "apps/api/app/modules/sharing/application/public_approval.py"
  );
  const changes = await read(
    "apps/api/app/modules/sharing/application/public_change_request.py"
  );
  const repository = await read(
    "apps/api/app/modules/sharing/infrastructure/change_request_repository.py"
  );
  assert.match(approval, /scope_status == "changes_requested"/);
  assert.match(changes, /scope_status == "approved"/);
  assert.match(repository, /with_for_update/);
  assert.match(repository, /status == "awaiting_approval"/);
  assert.match(repository, /values\(status="changes_requested"\)/);
});

test("0091 excludes comment and capability evidence from response and telemetry", async () => {
  const router = await read("apps/api/app/api/routers/public_scope_shares.py");
  const service = await read(
    "apps/api/app/modules/sharing/application/public_change_request.py"
  );
  const adr = await read("docs/adr/ADR-078-public-scope-change-request.md");
  assert.match(router, /change_request_id/);
  assert.doesNotMatch(router, /comment=change_request|version_hash=change_request/);
  assert.doesNotMatch(service, /emit\([\s\S]{0,450}comment=/);
  assert.doesNotMatch(service, /emit\([\s\S]{0,450}guest_name=/);
  assert.match(adr, /No new Scope Version/);
  assert.match(adr, /Unapproved assumptions:\*\* None/);
});
