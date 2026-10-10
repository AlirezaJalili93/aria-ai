import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("0086 provisioning freezes the two verified Standard-tier prices", async () => {
  const script = await read("scripts/db/provision_eval_prices.py");

  for (const value of [
    "openai-gpt-5.6-terra-standard-2026-07-30",
    "Decimal(\"2.00000000\")",
    "Decimal(\"0.20000000\")",
    "Decimal(\"12.00000000\")",
    "datetime(2026, 7, 30, tzinfo=UTC)",
    "google-gemini-3.8-flash-standard-intro-2026-09-02",
    "Decimal(\"0.75000000\")",
    "Decimal(\"0.07500000\")",
    "Decimal(\"3.75000000\")",
    "datetime(2026, 9, 2, tzinfo=UTC)",
  ]) {
    assert.ok(script.includes(value), `missing frozen Catalog value: ${value}`);
  }
});

test("0086 provisioning is explicit, atomic, idempotent and conflict-detecting", async () => {
  const script = await read("scripts/db/provision_eval_prices.py");

  assert.match(script, /ARIA_EVAL_DATABASE_CONFIRMED/);
  assert.match(script, /provision-0086-controlled-eval-prices/);
  assert.match(script, /async with engine\.begin\(\) as connection/);
  assert.match(script, /pg_advisory_xact_lock/);
  assert.match(script, /ON CONFLICT DO NOTHING/);
  assert.match(script, /catalog_rows_missing_or_conflicting/);
  assert.match(script, /SET LOCAL statement_timeout = '5s'/);
  assert.doesNotMatch(script, /UPDATE public\.provider_price_versions/i);
  assert.doesNotMatch(script, /DELETE FROM public\.provider_price_versions/i);
});

test("0086 provisioning logs no credential or database URL", async () => {
  const script = await read("scripts/db/provision_eval_prices.py");

  assert.doesNotMatch(script, /LOGGER\.(?:info|error|warning)\([^\n]*database_url/i);
  assert.doesNotMatch(script, /OPENAI_API_KEY|GEMINI_API_KEY/);
  assert.match(script, /error_type=%s/);
});
