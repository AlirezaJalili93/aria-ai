import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const router = readFileSync(resolve(root, "apps/api/app/api/routers/jobs.py"), "utf8");
const service = readFileSync(
  resolve(root, "apps/api/app/modules/jobs/application/job_status.py"),
  "utf8",
);
const repository = readFileSync(
  resolve(root, "apps/api/app/modules/jobs/infrastructure/repository.py"),
  "utf8",
);

test("Job status route exposes the approved public contract", () => {
  for (const field of ["id", "job_type", "status", "progress_stage", "retryable", "error"]) {
    assert.match(router, new RegExp(`\\b${field}\\b`));
  }
  assert.match(router, /router = APIRouter\(prefix="\/jobs"/);
  assert.match(router, /ResourceNotFoundError/);
  assert.doesNotMatch(router, /payload_ref|attempt_count|max_attempts|correlation_id/);
});

test("Job status reads are tenant scoped and defer retry policy", () => {
  assert.match(service, /get_for_account\(/);
  assert.match(repository, /JobModel\.account_id == account_id/);
  assert.match(service, /retryable=False/);
  assert.match(service, /progress_stage=None/);
});
