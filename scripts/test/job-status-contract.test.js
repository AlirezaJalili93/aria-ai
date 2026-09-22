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
  const publicDataModel = router.slice(
    router.indexOf("class JobStatusDataResponse"),
    router.indexOf("class JobStatusMetaResponse"),
  );
  for (const field of ["id", "job_type", "status", "progress_stage", "retryable", "error"]) {
    assert.match(publicDataModel, new RegExp(`\\b${field}\\b`));
  }
  assert.match(router, /router = APIRouter\(prefix="\/jobs"/);
  assert.match(router, /ResourceNotFoundError/);
  assert.doesNotMatch(
    publicDataModel,
    /payload_ref|attempt_count|max_attempts|correlation_id|retry_of_job_id/,
  );
});

test("Job status reads are tenant scoped and expose only the approved retry classification", () => {
  assert.match(service, /get_for_account\(/);
  assert.match(repository, /JobModel\.account_id == account_id/);
  assert.match(service, /job\.status == "failed"/);
  assert.match(service, /job\.job_type == "context_source_parse"/);
  assert.match(service, /job\.error_code == "PARSER_STORAGE_UNAVAILABLE"/);
  assert.doesNotMatch(service, /retryable=True/);
  assert.match(service, /progress_stage=None/);
});
