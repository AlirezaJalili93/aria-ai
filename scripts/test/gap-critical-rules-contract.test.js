import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("J02-B freezes the approved checklist and rule-pack versions", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );

  assert.match(application, /COMPLETION_CHECKLIST_VERSION = "completion_checklist_v1"/);
  assert.match(application, /CRITICAL_GAP_RULE_PACK_VERSION = "critical_gap_rule_pack_v1"/);
  for (const projectType of ["landing", "corporate", "portfolio"]) {
    assert.match(application, new RegExp(`"${projectType}"`));
  }
  for (const ruleId of ["CGR-001", "CGR-002", "CGR-003"]) {
    assert.match(application, new RegExp(`"${ruleId}"`));
  }
});

test("rule signals remain untrusted, provider-neutral AI evidence", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );

  assert.match(application, /class ChecklistItemRuleSignal/);
  assert.match(application, /class RequirementConflictRuleSignal/);
  assert.match(application, /class CriticalAssumptionRuleSignal/);
  assert.match(application, /signal_origin.*ai_candidate/s);
  assert.match(application, /incomplete_or_duplicate_checklist_signals/);
  assert.match(application, /requirement_conflict_requires_distinct_pair/);
  assert.match(application, /invalid_critical_assumption_subject/);
  assert.doesNotMatch(application, /openai|anthropic|gemini|celery|redis/i);
});

test("critical assignment is fail-closed and version-pinned", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );
  const repository = await read(
    "apps/api/app/modules/gaps/infrastructure/detection_repository.py",
  );

  assert.match(application, /GAP_CRITICAL_POLICY_UNAVAILABLE/);
  assert.match(application, /candidate\.severity == "critical"[\s\S]*?"high"/);
  assert.match(repository, /"completion_checklist_version": completion_checklist_version/);
  assert.match(repository, /"critical_rule_pack_version": critical_rule_pack_version/);
});

test("J02-B observability excludes raw AI and customer evidence", async () => {
  const application = await read(
    "packages/backend-application/src/aria_backend_application/gap_detection.py",
  );
  const emitSections = application.match(/self\._event_logger\.emit\([\s\S]{0,1200}?\n\s*\)/g) ?? [];
  const joined = emitSections.join("\n");

  for (const safeField of [
    "completion_checklist_version",
    "critical_rule_pack_version",
    "rule_generated_gap_count",
    "critical_gap_count",
    "matched_rule_count",
  ]) {
    assert.match(application, new RegExp(safeField));
  }
  assert.doesNotMatch(
    joined,
    /content|description|explanation|source_refs|rule_signals|response\.data|prompt\s*=/,
  );
});
