import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("OpenAPI publishes the approved text and feature-gated TXT Context contracts", async () => {
  const contract = await read("packages/contracts/openapi.yaml");

  assert.match(contract, /\/projects\/\{project_id\}\/context-sources:/);
  assert.match(contract, /operationId: createTextContextSource/);
  assert.match(contract, /source_type:\s*\{ type: string, const: text \}/);
  assert.match(contract, /raw_text:\s*\{ type: string, minLength: 1, maxLength: 50000 \}/);
  assert.match(contract, /multipart\/form-data:/);
  assert.match(contract, /source_type:\s*\{ type: string, const: file \}/);
  assert.match(contract, /format: binary/);
  assert.match(contract, /status:\s*\{ type: string, const: uploaded \}/);
  assert.match(contract, /required: \[source_id, status, job_id, status_url\]/);
  assert.match(contract, /pattern: \^\/api\/v1\/jobs\//);
  assert.match(contract, /IDEMPOTENCY_CONFLICT/);
  for (const value of ["FILE_TOO_LARGE", "UNSUPPORTED_FILE_TYPE", "STORAGE_ERROR"]) {
    assert.match(contract, new RegExp(value));
  }
});

test("TXT upload keeps provider coupling in Infrastructure and enforces fixed safety controls", async () => {
  const domain = await read("apps/api/app/modules/context/domain/file_upload.py");
  const useCase = await read(
    "apps/api/app/modules/context/application/file_context_ingestion.py"
  );
  const adapter = await read(
    "apps/api/app/modules/context/infrastructure/supabase_storage.py"
  );
  const config = await read("apps/api/app/core/config.py");

  assert.match(domain, /TXT_UPLOAD_MAX_BYTES = 200_000/);
  assert.match(domain, /TXT_UPLOAD_MAX_CHARACTERS = 50_000/);
  assert.match(domain, /decode\("utf-8", errors="strict"\)/);
  assert.match(useCase, /environment[\s\S]*account_id[\s\S]*project_id[\s\S]*source_id[\s\S]*version_id/);
  assert.match(useCase, /storage\.compensation_started/);
  assert.match(useCase, /storage\.compensation_failed/);
  assert.doesNotMatch(useCase, /from (boto3|supabase)/);
  assert.match(adapter, /STORAGE_CONNECT_TIMEOUT_SECONDS = 5/);
  assert.match(adapter, /STORAGE_READ_TIMEOUT_SECONDS = 30/);
  assert.match(adapter, /"total_max_attempts": 1/);
  assert.doesNotMatch(adapter, /public_url|signed_url|upsert/i);
  assert.match(config, /txt_upload_enabled: bool = False/);
});

test("ingestion keeps content out of Job and Outbox references", async () => {
  const useCase = await read(
    "apps/api/app/modules/context/application/text_context_ingestion.py"
  );

  assert.match(useCase, /TEXT_CONTEXT_JOB_TYPE = "context_source_parse"/);
  assert.match(
    useCase,
    /payload_ref=\{\s*"source_id"[\s\S]*"source_version_id"[\s\S]*\}/
  );
  assert.doesNotMatch(useCase, /payload_ref=\{[^}]*raw_text/);
  assert.match(useCase, /event_type="context_added\.v1"/);
});

test("generic idempotency storage uses the approved actor-aware scope", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0006_idempotency_records.py"
  );
  const useCase = await read(
    "apps/api/app/modules/context/application/text_context_ingestion.py"
  );

  assert.match(migration, /"account_id",\s*"actor_id",\s*"route_key",\s*"idempotency_key"/);
  assert.match(useCase, /timedelta\(hours=24\)/);
  assert.match(useCase, /"project_id": str\(project_id\)/);
  assert.match(useCase, /"raw_text": raw_text/);
});
