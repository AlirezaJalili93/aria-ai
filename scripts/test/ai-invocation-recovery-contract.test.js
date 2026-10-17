import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

test("0083 freezes durable normalized-result recovery without reinvocation", () => {
  const adr = read("docs/adr/ADR-069-durable-ai-invocation-recovery.md");
  const application = read(
    "packages/backend-application/src/aria_backend_application/ai_invocation_recovery.py",
  );
  const adapter = read(
    "apps/worker/app/infrastructure/db/ai_invocation_recovery.py",
  );

  assert.match(adr, /Status: Accepted/);
  assert.match(adr, /AI_INVOCATION_OUTCOME_UNKNOWN/);
  assert.match(adr, /No automatic Provider re-invocation/i);
  assert.match(application, /disposition="reuse_result"/);
  assert.match(application, /mark_outcome_unknown/);
  assert.match(adapter, /normalized_result=NULL/);
  assert.match(adapter, /usage_checkpoint_conflict/);
});

test("0083 migration protects transient content and least privilege", () => {
  const migration = read(
    "apps/api/migrations/versions/0031_ai_invocation_checkpoints.py",
  );
  const hosted = read("apps/worker/app/main.py");

  assert.match(migration, /ENABLE ROW LEVEL SECURITY/);
  assert.match(migration, /FORCE ROW LEVEL SECURITY/);
  assert.match(migration, /aria\.checkpoint_account_id/);
  assert.match(migration, /GRANT SELECT, INSERT, UPDATE/);
  assert.doesNotMatch(migration, /GRANT DELETE/);
  assert.match(migration, /outcome_unknown/);
  assert.doesNotMatch(hosted, /PostgresAIInvocationCheckpointStore/);
});
