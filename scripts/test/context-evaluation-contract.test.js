import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import {
  CLASS_NAMES,
  FakeDeterministicProvider,
  assessThreshold,
  calculateClassification,
  calculatePersianQuality,
  evaluateOutput,
  loadFixtures,
  runEvaluation
} from "../context-evaluation.mjs";

const root = process.cwd();
const evalRoot = path.join(root, "evals/context-structuring/context_structuring_eval_v1");

test("H05 contains exactly twenty versioned Persian synthetic fixtures", async () => {
  const manifest = JSON.parse(await readFile(path.join(evalRoot, "manifest.json"), "utf8"));
  const fixtureSchema = JSON.parse(await readFile(path.join(evalRoot, "schemas/fixture.schema.json"), "utf8"));
  const reportSchema = JSON.parse(await readFile(path.join(evalRoot, "schemas/report.schema.json"), "utf8"));
  const rubric = JSON.parse(await readFile(path.join(evalRoot, "human-review-rubric.json"), "utf8"));
  const fixtures = await loadFixtures(evalRoot);
  assert.equal(manifest.eval_set_id, "context_structuring_eval_v1");
  assert.equal(manifest.expected_fixture_count, 20);
  assert.equal(fixtures.length, 20);
  assert.deepEqual(fixtures.map((fixture) => fixture.fixture_id), manifest.fixture_ids);
  assert.ok(fixtureSchema.required.includes("provenance_expectations"));
  assert.ok(reportSchema.required.includes("model_quality_gate"));
  assert.equal(rubric.reviewer_count, 2);
  assert.equal(rubric.fixture_pass.minimum_mean, 4);
  for (const fixture of fixtures) {
    assert.equal(fixture.language, "fa");
    assert.equal(fixture.metadata.synthetic, true);
    assert.equal(fixture.eval_set_id, manifest.eval_set_id);
  }
});

test("fake deterministic provider produces a stable contract report without raw content", async () => {
  const report = await runEvaluation({ root: evalRoot, provider: new FakeDeterministicProvider() });
  assert.equal(report.provider_mode, "fake_deterministic");
  assert.equal(report.fixture_count, 20);
  assert.equal(report.metrics.source_trace_rate.value, 1);
  assert.equal(report.metrics.unsupported_assumption_rate.value, 0);
  assert.equal(report.metrics.first_pass_valid_rate.value, 1);
  assert.equal(report.metrics.json_validity_after_repair.value, 1);
  assert.equal(report.metrics.classification.accuracy.value, 1);
  assert.equal(report.metrics.classification.macro_f1, 5 / 6);
  assert.equal(report.threshold_assessments.source_trace_rate, "target");
  assert.equal(report.threshold_assessments.classification_macro_f1, "minimum_acceptable");
  assert.deepEqual(report.contract_gate, { status: "pass" });
  assert.deepEqual(report.model_quality_gate, { status: "not_run", reason: "real_provider_and_human_review_required" });
  assert.equal(report.fixtures.find((fixture) => fixture.fixture_id === "fa_ctx_015").outcome, "fail");
  assert.doesNotMatch(JSON.stringify(report), /کافه|کلینیک|prompt|system prompt/i);
});

test("classification accuracy uses gold count plus unmatched predicted count", () => {
  const gold = [{ gold_item_id: "g1", item_type: "fact" }];
  const predicted = [
    { item_id: "g1", item_type: "assumption" },
    { item_id: "p2", item_type: "unknown" }
  ];
  const result = calculateClassification(gold, predicted);
  assert.equal(result.aligned_decisions, 2);
  assert.equal(result.correct, 0);
  assert.equal(result.accuracy, 0);
  assert.deepEqual(Object.keys(result.per_class), CLASS_NAMES);
});

test("provenance and unsupported-assumption checks reject unsafe fake output", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const fixture = fixtures.find((item) => item.fixture_id === "fa_ctx_017");
  const unsafe = {
    items: [{
      item_id: "fa_ctx_017_a1",
      item_type: "assumption",
      content: "تضمین رتبه اول گوگل",
      source_refs: []
    }],
    failure: null,
    repair_attempted: false
  };
  const result = evaluateOutput(fixture, unsafe);
  assert.ok(result.failure_categories.includes("missing_required_trace"));
  assert.equal(result.unsupported_assumptions.unsupported, 1);
  assert.equal(result.source_trace.valid, 0);
});

test("malformed provider items become contract failures instead of crashing the evaluator", async () => {
  const [fixture] = await loadFixtures(evalRoot);
  const result = evaluateOutput(fixture, { items: [null, { item_id: "broken", item_type: "invalid" }], failure: null });
  assert.ok(result.failure_categories.includes("invalid_item_identity"));
  assert.ok(result.failure_categories.includes("invalid_item_type"));
  assert.equal(result.first_pass_valid, false);
  assert.equal(result.classification.accuracy, 0);
});

test("Persian quality remains human-review input and uses the approved 1–5 formula", () => {
  assert.deepEqual(calculatePersianQuality([]), { value: null, numerator: 0, denominator: 0, status: "not_run" });
  assert.deepEqual(calculatePersianQuality([4, 5]), { value: 0.9, numerator: 9, denominator: 2, status: "scored" });
});

test("approved threshold directions are executable without claiming model quality", async () => {
  const thresholds = JSON.parse(await readFile(path.join(evalRoot, "thresholds.json"), "utf8"));
  assert.equal(assessThreshold(0.99, thresholds.metrics.source_trace_rate), "target");
  assert.equal(assessThreshold(0.92, thresholds.metrics.source_trace_rate), "below_minimum");
  assert.equal(assessThreshold(0.89, thresholds.metrics.source_trace_rate), "release_blocker");
  assert.equal(assessThreshold(0.05, thresholds.metrics.unsupported_assumption_rate), "target");
  assert.equal(assessThreshold(0.11, thresholds.metrics.unsupported_assumption_rate), "release_blocker");
  assert.equal(assessThreshold(null, thresholds.metrics.persian_quality_raw_mean), "not_run");
});

test("ADR-029 is accepted and keeps the executable accuracy definition", async () => {
  const adr = await readFile(path.join(root, "docs/adr/ADR-029-context-evaluation-set-contract.md"), "utf8");
  assert.match(adr, /Status:\*\* Accepted/);
  assert.match(adr, /aligned_decisions = \|gold_items\| \+ \|unmatched_predicted_items\|/);
  assert.match(adr, /accuracy\s+= correctly classified one-to-one matches \/ aligned_decisions/);
});
