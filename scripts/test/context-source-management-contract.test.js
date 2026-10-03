import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

test("0065 records the approved Source query and archive contract", () => {
  const adr = read("docs/adr/ADR-052-context-source-management-and-retry.md");
  assert.match(adr, /GET \/api\/v1\/projects\/\{project_id\}\/context-sources/);
  assert.match(adr, /Owner\/Admin/);
  assert.match(adr, /Member.*created_by/s);
  assert.match(adr, /Storage object.*preserved/i);
  assert.match(adr, /raw_text.*canonical_text.*storage_ref/s);
});

test("0065 exposes query, detail, archive and explicit retry routes", () => {
  const sources = read("apps/api/app/api/routers/context_sources.py");
  const jobs = read("apps/api/app/api/routers/jobs.py");
  assert.match(sources, /@router\.get\(""/);
  assert.match(sources, /@router\.get\("\/\{source_id\}"/);
  assert.match(sources, /@router\.delete\("\/\{source_id\}"/);
  assert.match(jobs, /@router\.post\(\s*"\/\{job_id\}\/retry"/);
  for (const forbidden of ["raw_text", "canonical_text", "storage_ref", "object_key"]) {
    assert.doesNotMatch(sources.match(/class ContextSourceSummaryResponse[\s\S]*?def _text_context_use_case/)[0], new RegExp(`\\n\\s+${forbidden}:`));
  }
});

test("0065 persists immediate retry lineage and one active parser Job per SourceVersion", () => {
  const migration = read("apps/api/migrations/versions/0022_context_source_management.py");
  assert.match(migration, /retry_of_job_id/);
  assert.match(migration, /ondelete\s*=\s*"RESTRICT"/);
  assert.match(migration, /uq_jobs_retry_of_job_id/);
  assert.match(migration, /uq_jobs_active_context_source_version/);
  assert.match(migration, /queued.*running/s);
});

test("0065 keeps automatic retry, relay scheduling and physical Storage GC deferred", () => {
  const adr = read("docs/adr/ADR-052-context-source-management-and-retry.md");
  assert.match(adr, /automatic_retry = disabled/);
  assert.match(adr, /Continuous Outbox.*deferred/i);
  assert.match(adr, /Physical Storage GC.*deferred/i);
});
