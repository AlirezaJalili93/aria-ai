import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

test("0085 freezes a known timeout separately from an ambiguous outcome", () => {
  const adr = read(
    "docs/adr/ADR-071-durable-technical-retry-checkpoint-integration.md",
  );
  const migration = read(
    "apps/api/migrations/versions/0033_durable_technical_retry_checkpoint.py",
  );

  assert.match(adr, /Status: Accepted/);
  assert.match(adr, /failed_known/);
  assert.match(adr, /outcome_unknown/);
  assert.match(migration, /retry_not_before/);
  assert.match(migration, /failure_class='timeout'/);
  assert.match(migration, /OLD\.status='started'.*'failed_known'/s);
});

test("0085 keeps the synthetic invocation budget at two without fallback", () => {
  const runtime = read(
    "apps/worker/app/infrastructure/ai/context_structuring_checkpoint.py",
  );
  const application = read(
    "packages/backend-application/src/aria_backend_application/context_structuring.py",
  );

  assert.match(runtime, /retry_no=1/);
  assert.match(runtime, /error_class != "timeout"/);
  assert.match(runtime, /_full_jitter_delay/);
  assert.match(application, /checkpoint_failure/);
  assert.doesNotMatch(runtime, /fallback/i);
});
