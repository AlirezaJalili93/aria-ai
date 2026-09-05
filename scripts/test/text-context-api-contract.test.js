import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("OpenAPI publishes only the approved text Context ingestion contract", async () => {
  const contract = await read("packages/contracts/openapi.yaml");

  assert.match(contract, /\/projects\/\{project_id\}\/context-sources:/);
  assert.match(contract, /operationId: createTextContextSource/);
  assert.match(contract, /source_type:\s*\{ type: string, const: text \}/);
  assert.match(contract, /raw_text:\s*\{ type: string, minLength: 1, maxLength: 50000 \}/);
  assert.match(contract, /status:\s*\{ type: string, const: uploaded \}/);
  assert.match(contract, /IDEMPOTENCY_CONFLICT/);
  assert.match(
    contract,
    /\/projects\/\{project_id\}\/context-sources:[\s\S]*MembershipRequired/
  );
  assert.doesNotMatch(contract, /context-sources[\s\S]{0,500}source_type.*file/);
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
