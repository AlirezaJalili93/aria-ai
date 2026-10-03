import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0063 freezes the complete TXT upload security matrix without expanding product scope", async () => {
  const adr = await read("docs/adr/ADR-050-upload-security-suite.md");
  const record = await read(
    "docs/development/0063-upload-security-suite/development.md"
  );

  for (const requirement of [
    "REQ-6301",
    "REQ-6302",
    "REQ-6303",
    "REQ-6304",
    "REQ-6305",
    "REQ-6306",
    "REQ-6307",
    "REQ-6308",
  ]) {
    assert.match(record, new RegExp(requirement));
  }
  assert.match(adr, /No executable keyword blacklist/);
  assert.match(adr, /hosted check must separately prove/);
  assert.match(adr, /TXT_UPLOAD_ENABLED.*stays false/s);
  assert.match(adr, /Context Inbox UI/);
});

test("private storage boundary exposes no public, signed, ACL or upsert capability", async () => {
  const port = await read(
    "apps/api/app/modules/context/application/file_upload_ports.py"
  );
  const adapter = await read(
    "apps/api/app/modules/context/infrastructure/supabase_storage.py"
  );
  const api = await read("packages/contracts/openapi.yaml");

  assert.match(port, /put_private/);
  assert.doesNotMatch(port, /public_url|signed_url|download/i);
  assert.doesNotMatch(adapter, /public_url|signed_url|upsert|ACL/);
  assert.doesNotMatch(api, /storage_ref|object_key|public_url|signed_url/);
});

test("security tests cover malicious input, tenant, retry, compensation and leakage", async () => {
  const domainTests = await read("apps/api/tests/test_file_upload_domain.py");
  const apiTests = await read("apps/api/tests/test_file_context_api.py");
  const applicationTests = await read(
    "apps/api/tests/test_file_context_ingestion.py"
  );
  const postgresTests = await read("apps/api/tests/test_file_context_postgres.py");
  const storageTests = await read("apps/api/tests/test_supabase_storage.py");
  const hostedTests = await read("apps/api/tests/test_upload_security_hosted.py");

  assert.match(domainTests, /mime_spoofing/);
  assert.match(domainTests, /binary_executable/);
  assert.match(domainTests, /path_traversal/);
  assert.match(apiTests, /feature_flag_is_off/);
  assert.match(apiTests, /response_never_exposes_storage/);
  assert.match(applicationTests, /same_semantic_upload_replays/);
  assert.match(applicationTests, /cleanup_failure_is_a_safe_discoverable_incident/);
  assert.match(postgresTests, /cross_tenant_project/);
  assert.match(storageTests, /without_public_url_acl_or_upsert/);
  assert.match(hostedTests, /denies_anonymous_access/);
  assert.match(hostedTests, /RUN_HOSTED_UPLOAD_SECURITY/);
});

test("the Staging TXT upload default remains fail-closed", async () => {
  const env = await read(".env.example");
  const railway = await read("infra/railway/README.md");
  const config = await read("apps/api/app/core/config.py");

  assert.match(env, /^TXT_UPLOAD_ENABLED=false$/m);
  assert.match(railway, /TXT_UPLOAD_ENABLED=false/);
  assert.match(config, /txt_upload_enabled: bool = False/);
});

test("unknown PutObject outcomes retain a stable durable upload allocation", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0020_file_upload_allocations.py"
  );
  const port = await read(
    "apps/api/app/modules/context/application/file_upload_ports.py"
  );
  const useCase = await read(
    "apps/api/app/modules/context/application/file_context_ingestion.py"
  );

  for (const status of [
    "allocated",
    "uploading",
    "committed",
    "recovery_required",
  ]) {
    assert.match(migration, new RegExp(status));
  }
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /anon.*authenticated/s);
  assert.match(port, /source_id: UUID/);
  assert.match(port, /source_version_id: UUID/);
  assert.match(port, /object_key: str/);
  assert.match(useCase, /recovery_required.*outcome_unknown|outcome_unknown.*recovery_required/s);
  assert.doesNotMatch(useCase, /\.idempotency\./);
});
