import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("J02-A migration extends Gap persistence and creates tenant-safe links", async () => {
  const migration = await read("apps/api/migrations/versions/0015_gap_detection.py");

  assert.match(migration, /down_revision:\s*str\s*\|\s*None\s*=\s*["']0014_gaps["']/);
  for (const field of ["explanation", "suggested_resolution_type", "generation_job_id"]) {
    assert.match(migration, new RegExp(`["']${field}["']`));
  }
  assert.match(migration, /gap_requirement_links/);
  assert.match(migration, /PRIMARY KEY|PrimaryKeyConstraint/);
  assert.match(migration, /ondelete=["']RESTRICT["']/g);
  assert.match(migration, /ALTER TABLE gap_requirement_links ENABLE ROW LEVEL SECURITY/);
  assert.doesNotMatch(migration, /affected_requirement_ids.*JSONB|gap_generation_results/i);
});
test("Application contract stays provider-neutral while extending J02-A", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );

  assert.match(application, /class CriticalGapRuleEvaluator\(Protocol\)/);
  assert.match(application, /GAP_SNAPSHOT_CHANGED/);
  assert.match(application, /DUPLICATE_GAP/);
  assert.match(application, /gap\.detection_started/);
  assert.match(application, /gap\.replay_served/);
  assert.doesNotMatch(application, /openai|anthropic|gemini|celery|redis/i);
});

test("ADR keeps J02-B and questions out of the foundation", async () => {
  const adr = await read("docs/adr/ADR-036-gap-detection-foundation.md");
  const openapi = await read("packages/contracts/openapi.yaml");

  assert.match(adr, /This ADR records the J02-A boundary/);
  assert.match(adr, /ADR-037 later approved and specifies J02-B/);
  assert.match(adr, /J02-A contains no rule implementation/);
  assert.match(adr, /J03: question/);
  assert.doesNotMatch(openapi, /gap-detection|\/gaps/);
});

test("Gap detection logs cannot include customer content or model payloads", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );
  for (const event of [
    "gap.detection_started",
    "gap.detection_completed",
    "gap.detection_failed",
    "gap.snapshot_changed",
    "gap.duplicate_rejected",
    "gap.replay_served",
  ]) {
    assert.match(application, new RegExp(`["]${event.replaceAll(".", "\\.")}["]`));
  }
  const emitSections = application.match(/self\._event_logger\.emit\([\s\S]{0,900}?\n\s*\)/g) ?? [];
  const joined = emitSections.join("\n");
  assert.doesNotMatch(joined, /explanation|source_refs|affected_requirement_ids|input_context|response\.data/);
});
