import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

test("0084 freezes one-attempt AI-01 checkpoint recovery", () => {
  const adr = read("docs/adr/ADR-070-ai01-durable-checkpoint-integration.md");
  const codec = read(
    "packages/backend-application/src/aria_backend_application/context_structuring_checkpoint.py",
  );
  const runtime = read(
    "apps/worker/app/infrastructure/ai/context_structuring_checkpoint.py",
  );

  assert.match(adr, /Status: Accepted/);
  assert.match(adr, /retry_no=0/);
  assert.match(adr, /repair_no=0/);
  assert.match(codec, /context_structuring_checkpoint_v1/);
  assert.match(codec, /content_hash/);
  assert.doesNotMatch(codec, /"rationale_short":/);
  assert.match(runtime, /AI_INVOCATION_CHECKPOINT_INVALID/);
  assert.match(runtime, /AI_INVOCATION_OUTCOME_UNKNOWN/);
});

test("0084 finalizes checkpoint with Context and Job in one transaction", () => {
  const repository = read(
    "apps/worker/app/infrastructure/db/context_structuring_runtime.py",
  );
  const useCase = read(
    "packages/backend-application/src/aria_backend_application/context_structuring.py",
  );
  const hosted = read("apps/worker/app/main.py");

  assert.match(repository, /finalize_invocation_checkpoint/);
  assert.match(repository, /normalized_result=NULL/);
  assert.match(useCase, /complete_job_success/);
  assert.match(useCase, /finalize_invocation_checkpoint/);
  assert.match(useCase, /await unit_of_work\.commit\(\)/);
  assert.doesNotMatch(hosted, /SyntheticAI01CheckpointRuntime/);
});
