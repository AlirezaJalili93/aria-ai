import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("provider price catalog is immutable, deterministic and runtime read-only", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0023_provider_price_versions.py",
  );

  for (const field of [
    "provider",
    "model",
    "pricing_version",
    "currency",
    "input_rate_per_1m",
    "cached_input_rate_per_1m",
    "output_rate_per_1m",
    "effective_from",
    "created_at",
  ]) {
    assert.match(migration, new RegExp(`['\"]${field}['\"]`));
  }

  assert.match(migration, /uq_provider_prices_identity/);
  assert.match(migration, /uq_provider_prices_effective_from/);
  assert.match(migration, /BEFORE UPDATE OR DELETE ON provider_price_versions/);
  assert.match(
    migration,
    /GRANT SELECT ON TABLE public\.provider_price_versions TO aria_worker/,
  );
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /FOR SELECT\s+TO aria_worker\s+USING \(true\)/s);
  assert.match(migration, /anon.*authenticated.*aria_api/s);
  assert.doesNotMatch(migration, /INSERT INTO provider_price_versions/i);
  assert.doesNotMatch(migration, /service_role/i);
});

test("Usage Ledger is bound to catalog identity and token accounting is guarded", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0023_provider_price_versions.py",
  );

  assert.match(migration, /fk_usage_records_provider_price/);
  assert.match(
    migration,
    /FOREIGN KEY \(provider, model, pricing_version\)[\s\S]*REFERENCES provider_price_versions \(provider, model, pricing_version\)/,
  );
  assert.match(migration, /cached_input_tokens <= input_tokens/);
  assert.match(migration, /ON DELETE RESTRICT NOT VALID/);
});

test("pricing Application contract owns deterministic resolution and Decimal calculation", async () => {
  const pricing = await read(
    "packages/backend-application/src/aria_backend_application/provider_pricing.py",
  );
  const adapter = await read("apps/worker/app/infrastructure/db/provider_pricing.py");
  const openapi = await read("packages/contracts/openapi.yaml");

  assert.match(pricing, /class ProviderPriceCatalog\(Protocol\)/);
  assert.match(pricing, /async def resolve\(/);
  assert.match(pricing, /ROUND_HALF_UP/);
  assert.match(pricing, /Decimal\(1000000\)/);
  assert.match(pricing, /cached_input_tokens > usage\.input_tokens/);
  assert.match(pricing, /def price_usage_record\(/);
  assert.doesNotMatch(pricing, /sqlalchemy|asyncpg|fastapi|supabase|openai|anthropic|gemini/i);

  assert.match(adapter, /effective_from <= provider_execution_at/);
  assert.match(adapter, /effective_from\.desc\(\)/);
  assert.match(adapter, /limit\(1\)/);
  assert.doesNotMatch(adapter, /insert\(|update\(|delete\(/i);
  assert.doesNotMatch(openapi, /provider-price|provider_price|pricing-version/i);
});
