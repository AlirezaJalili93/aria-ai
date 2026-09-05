import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("logical M009 creates only the approved append-only Usage Ledger", async () => {
  const migration = await read("apps/api/migrations/versions/0007_usage_records.py");

  for (const field of [
    "account_id",
    "project_id",
    "job_id",
    "task_type",
    "workflow_version",
    "prompt_version",
    "provider",
    "model",
    "provider_request_id",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "latency_ms",
    "status",
    "error_code",
    "retry_no",
    "estimated_cost",
    "currency",
    "pricing_version",
    "correlation_id",
    "created_at",
  ]) {
    assert.match(migration, new RegExp(`['\"]${field}['\"]`));
  }

  assert.match(migration, /NUMERIC\(precision=14, scale=3\)/);
  assert.match(migration, /NUMERIC\(precision=14, scale=8\)/);
  assert.match(migration, /success','failed','partial/);
  assert.match(migration, /prevent_usage_record_mutation/);
  assert.match(migration, /BEFORE UPDATE OR DELETE ON usage_records/);
  assert.doesNotMatch(migration, /provider_price_versions|attempt_no/);
  assert.doesNotMatch(migration, /estimated_cost[^\n]+server_default/);
});

test("Usage Ledger database authority is worker-only and fail-closed", async () => {
  const migration = await read("apps/api/migrations/versions/0007_usage_records.py");

  assert.match(migration, /aria_worker/);
  assert.match(migration, /NOBYPASSRLS/);
  assert.match(migration, /GRANT INSERT ON TABLE public\.usage_records TO aria_worker/);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /FOR INSERT\s+TO aria_worker\s+WITH CHECK \(true\)/s);
  assert.match(migration, /anon.*authenticated.*aria_api/s);
  assert.match(migration, /ondelete="RESTRICT"/);
  assert.doesNotMatch(migration, /service_role/i);
  assert.doesNotMatch(migration, /(^|\s)BYPASSRLS(\s|;|$)/im);
});

test("UsageLedger Application port remains provider-neutral and append-only", async () => {
  const application = await read("apps/worker/app/application/usage_ledger.py");
  const adapter = await read("apps/worker/app/infrastructure/db/usage_ledger.py");
  const openapi = await read("packages/contracts/openapi.yaml");

  assert.match(application, /class UsageLedger\(Protocol\)/);
  assert.match(application, /async def append\(self, record: UsageRecord\) -> None/);
  assert.doesNotMatch(application, /sqlalchemy|asyncpg|fastapi|supabase|openai|anthropic|gemini/i);
  assert.match(adapter, /insert\(usage_records\)/);
  assert.match(adapter, /implicit_returning=False/);
  assert.doesNotMatch(adapter, /if\s+.*provider|update\(|delete\(|select\(/i);
  assert.doesNotMatch(openapi, /usage_records|UsageRecord|\/api\/v1\/usage/i);
});
