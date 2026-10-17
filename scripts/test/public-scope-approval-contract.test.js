import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0090 exposes body-token public approval with exact consent and guest idempotency", async () => {
  const router = await read("apps/api/app/api/routers/public_scope_shares.py");
  assert.match(router, /@router\.post\([\s\S]*"\/approve"/);
  assert.match(router, /Header\(alias="Idempotency-Key"\)/);
  assert.match(router, /StrictBool/);
  assert.match(router, /explicit_consent must be true/);
  assert.doesNotMatch(router, /approve.*\{token\}/);
});

test("0090 persists exact snapshot evidence and atomic Scope lifecycle transition", async () => {
  const migration = await read("apps/api/migrations/versions/0035_scope_approvals.py");
  const repository = await read(
    "apps/api/app/modules/sharing/infrastructure/approval_repository.py"
  );
  assert.match(migration, /version_hash/);
  assert.match(migration, /UniqueConstraint\("scope_version_id"/);
  assert.match(migration, /explicit_consent IS TRUE/);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(repository, /status == "awaiting_approval"/);
  assert.match(repository, /values\(status="approved"\)/);
});

test("0090 keeps response and observability free of capability and version hashes", async () => {
  const router = await read("apps/api/app/api/routers/public_scope_shares.py");
  const service = await read("apps/api/app/modules/sharing/application/public_approval.py");
  assert.match(router, /approval_id/);
  assert.match(router, /scope_version_no/);
  assert.doesNotMatch(router, /version_hash=approval|token_hash=approval/);
  assert.doesNotMatch(service, /emit\([\s\S]{0,400}guest_name=/);
  assert.doesNotMatch(service, /emit\([\s\S]{0,400}version_hash=/);
});

test("0090 records the accepted final contract and explicit exclusions", async () => {
  const adr = await read("docs/adr/ADR-077-public-scope-approval.md");
  assert.match(adr, /Status:\*\* Accepted/);
  assert.match(adr, /SCOPE_ALREADY_APPROVED/);
  assert.match(adr, /Project status is unchanged/);
  assert.match(adr, /does not revoke the Share Link/);
  assert.match(adr, /Unapproved assumptions:\*\* None/);
});
