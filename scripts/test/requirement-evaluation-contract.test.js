import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import {
  CATEGORIES,
  FakeDeterministicProvider,
  assessThreshold,
  calculateHumanReview,
  evaluateOutput,
  loadFixtures,
  runEvaluation,
  validateFixtureContract
} from "../requirement-evaluation.mjs";

const root = process.cwd();
const evalRoot = path.join(root, "evals/requirement-extraction/requirement_extraction_eval_v1");

test("I05 contains exactly twenty immutable Persian synthetic fixtures", async () => {
  const manifest = JSON.parse(await readFile(path.join(evalRoot, "manifest.json"), "utf8"));
  const fixtureSchema = JSON.parse(await readFile(path.join(evalRoot, "schemas/fixture.schema.json"), "utf8"));
  const reportSchema = JSON.parse(await readFile(path.join(evalRoot, "schemas/report.schema.json"), "utf8"));
  const rubric = JSON.parse(await readFile(path.join(evalRoot, "human-review-rubric.json"), "utf8"));
  const fixtures = await loadFixtures(evalRoot);

  assert.equal(manifest.eval_set_id, "requirement_extraction_eval_v1");
  assert.equal(manifest.expected_fixture_count, 20);
  assert.equal(manifest.immutability, "gold_change_requires_new_eval_set_version");
  assert.deepEqual(fixtures.map((fixture) => fixture.fixture_id), manifest.fixture_ids);
  assert.deepEqual(manifest.fixture_ids, Array.from({ length: 20 }, (_, index) => `fa_req_${String(index + 1).padStart(3, "0")}`));
  assert.equal(fixtureSchema.properties.eval_set_id.const, manifest.eval_set_id);
  assert.equal(reportSchema.properties.provider_mode.const, "fake_deterministic");
  assert.equal(reportSchema.properties.metrics.additionalProperties, false);
  assert.deepEqual(Object.keys(reportSchema.properties.metrics.properties).sort(), [
    "actionability_score", "clarity_score", "critical_omission_rate", "duplicate_rate",
    "requirement_recall", "unsupported_detection_rate", "unsupported_output_rate"
  ]);
  assert.equal(rubric.reviewer_count, 2);
  assert.equal(rubric.adjudication.required_when_absolute_difference_at_least, 2);
  for (const fixture of fixtures) {
    assert.equal(fixture.language, "fa");
    assert.equal(fixture.metadata.synthetic, true);
    assert.equal(fixture.metadata.fixture_version, "1");
  }
});

test("fixture coverage includes every approved project type, category and risk segment", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const projectTypes = new Set(fixtures.map((fixture) => fixture.project_type));
  const categories = new Set(fixtures.flatMap((fixture) => fixture.expected_output.requirements.map((item) => item.category)));
  const segments = new Set(fixtures.map((fixture) => fixture.metadata.segment));

  assert.deepEqual([...projectTypes].sort(), ["corporate", "landing", "portfolio"]);
  assert.deepEqual([...categories].sort(), [...CATEGORIES].sort());
  for (const segment of ["clear", "ambiguous", "incomplete", "contradictory", "unsupported", "duplicate_potential", "mixed"]) {
    assert.ok(segments.has(segment), `missing ${segment}`);
  }
});

test("runtime fixture validation enforces unique deterministic candidate IDs", async () => {
  const [fixture] = await loadFixtures(evalRoot);
  const duplicateId = fixture.evaluation_annotations.deterministic_output_candidate_ids[0];
  const invalid = structuredClone(fixture);
  invalid.evaluation_annotations.deterministic_output_candidate_ids.push(duplicateId);

  assert.throws(() => validateFixtureContract(invalid), /duplicate_deterministic_candidate/);
});

test("Fake Provider produces a safe deterministic contract report without claiming model quality", async () => {
  const report = await runEvaluation({ root: evalRoot, provider: new FakeDeterministicProvider() });
  assert.equal(report.fixture_count, 20);
  assert.deepEqual(report.metrics.requirement_recall, { value: 1, numerator: 27, denominator: 27 });
  assert.deepEqual(report.metrics.critical_omission_rate, { value: 0, numerator: 0, denominator: 22 });
  assert.deepEqual(report.metrics.unsupported_output_rate, { value: 2 / 27, numerator: 2, denominator: 27 });
  assert.deepEqual(report.metrics.unsupported_detection_rate, { value: 1, numerator: 2, denominator: 2 });
  assert.deepEqual(report.metrics.duplicate_rate, { value: 0, numerator: 0, denominator: 27 });
  assert.equal(report.contract_gate.status, "pass");
  assert.deepEqual(report.model_quality_gate, { status: "not_run", reason: "real_provider_and_human_review_required" });
  assert.equal(report.human_review_status, "not_run");
  assert.equal(report.threshold_assessments.clarity_score, "not_run");
});

test("CI matching is annotation-driven and never depends on text similarity", async () => {
  const [fixture] = await loadFixtures(evalRoot);
  const output = await new FakeDeterministicProvider().execute(fixture);
  output.requirements[0].title = "متنی عمداً متفاوت برای اثبات نبود similarity judge";
  const result = evaluateOutput(fixture, output);

  assert.equal(result.counts.matched_gold, 1);
  assert.equal(result.counts.gold, 1);
  assert.deepEqual(result.failure_categories, []);
});

test("an unmatched critical Gold Requirement is an item-level release blocker", async () => {
  const [fixture] = await loadFixtures(evalRoot);
  const result = evaluateOutput(fixture, { requirements: [] });

  assert.equal(result.counts.omitted_critical, 1);
  const provider = { mode: "fake_deterministic", async execute(current) {
    return current.fixture_id === fixture.fixture_id ? { requirements: [] } : new FakeDeterministicProvider().execute(current);
  } };
  const report = await runEvaluation({ root: evalRoot, provider });
  assert.ok(report.critical_blockers.includes("critical_gold_unmatched"));
});

test("unsupported output quality and safety detection remain separate", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const fixture = fixtures.find((item) => item.fixture_id === "fa_req_016");
  const output = await new FakeDeterministicProvider().execute(fixture);
  output.requirements[0].is_unsupported = false;
  const result = evaluateOutput(fixture, output);

  assert.equal(result.counts.unsupported, 1);
  assert.equal(result.counts.detected_unsupported, 0);
  assert.equal(result.counts.critical_unsupported_misses, 1);

  const provider = { mode: "fake_deterministic", async execute(current) {
    const currentOutput = await new FakeDeterministicProvider().execute(current);
    if (current.fixture_id === fixture.fixture_id) currentOutput.requirements[0].is_unsupported = false;
    return currentOutput;
  } };
  const report = await runEvaluation({ root: evalRoot, provider });
  assert.ok(report.critical_blockers.includes("critical_unsupported_not_detected"));
});

test("zero generated output yields the frozen N/A metrics and does not pass quality", async () => {
  const provider = { mode: "fake_deterministic", async execute() { return { requirements: [] }; } };
  const report = await runEvaluation({ root: evalRoot, provider });

  assert.equal(report.metrics.requirement_recall.value, 0);
  assert.equal(report.metrics.critical_omission_rate.value, 1);
  assert.equal(report.metrics.unsupported_output_rate.value, null);
  assert.equal(report.metrics.unsupported_detection_rate.value, null);
  assert.equal(report.metrics.duplicate_rate.value, null);
  assert.equal(report.metrics.clarity_score.value, null);
  assert.equal(report.metrics.actionability_score.value, null);
  assert.equal(report.threshold_assessments.unsupported_detection_rate, "not_run");
  assert.ok(report.critical_blockers.includes("critical_gold_unmatched"));
});

test("duplicate rate counts only extra annotated members of a semantic group", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const fixture = fixtures.find((item) => item.fixture_id === "fa_req_008");
  const output = await new FakeDeterministicProvider().execute(fixture);
  output.requirements.push({ ...output.requirements[0], candidate_id: "fa_req_008_cand_duplicate" });
  const result = evaluateOutput(fixture, output);

  assert.equal(result.counts.generated, 2);
  assert.equal(result.counts.matched_gold, 1);
  assert.equal(result.counts.duplicate_extras, 1);
});

test("human review freezes zero-output N/A and difference-two adjudication", () => {
  const empty = calculateHumanReview({ generatedCandidateIds: [], records: [] });
  assert.equal(empty.status, "not_applicable");
  assert.equal(empty.clarity_score.value, null);
  assert.equal(empty.actionability_score.value, null);

  const pending = calculateHumanReview({
    generatedCandidateIds: ["candidate-1"],
    records: [{
      candidate_id: "candidate-1",
      reviewers: [
        { reviewer_id: "reviewer-1", clarity_score: 2, actionability_score: 3 },
        { reviewer_id: "reviewer-2", clarity_score: 4, actionability_score: 4 }
      ]
    }]
  });
  assert.equal(pending.status, "adjudication_required");

  const scored = calculateHumanReview({
    generatedCandidateIds: ["candidate-1"],
    criticalCandidateIds: ["candidate-1"],
    records: [{
      candidate_id: "candidate-1",
      reviewers: [
        { reviewer_id: "reviewer-1", clarity_score: 2, actionability_score: 4 },
        { reviewer_id: "reviewer-2", clarity_score: 4, actionability_score: 5 }
      ],
      adjudication: { clarity_score: 2 }
    }]
  });
  assert.equal(scored.status, "scored");
  assert.equal(scored.clarity_score.value, 2);
  assert.equal(scored.actionability_score.value, 4.5);
  assert.equal(scored.critical_clarity_below_3, true);
});

test("human review input rejects free-text notes", () => {
  assert.throws(() => calculateHumanReview({
    generatedCandidateIds: ["candidate-1"],
    records: [{
      candidate_id: "candidate-1",
      reviewer_free_text_notes: "must never enter a report",
      reviewers: [
        { reviewer_id: "reviewer-1", clarity_score: 5, actionability_score: 5 },
        { reviewer_id: "reviewer-2", clarity_score: 5, actionability_score: 5 }
      ]
    }]
  }), /Invalid human review record fields/);
});

test("critical human score blockers propagate to the final report", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const records = fixtures.flatMap((fixture) => {
    const annotations = new Map(fixture.evaluation_annotations.candidate_annotations.map((item) => [item.candidate_id, item]));
    return fixture.evaluation_annotations.deterministic_output_candidate_ids.map((candidateId, index) => {
      const critical = annotations.get(candidateId).critical_for_scope;
      const lowCritical = critical && fixture.fixture_id === "fa_req_001" && index === 0;
      return {
        candidate_id: candidateId,
        reviewers: [
          { reviewer_id: "reviewer-1", clarity_score: lowCritical ? 2 : 5, actionability_score: lowCritical ? 2 : 5 },
          { reviewer_id: "reviewer-2", clarity_score: lowCritical ? 2 : 5, actionability_score: lowCritical ? 2 : 5 }
        ]
      };
    });
  });
  const report = await runEvaluation({ root: evalRoot, humanReviewRecords: records });

  assert.ok(report.critical_blockers.includes("critical_clarity_below_3"));
  assert.ok(report.critical_blockers.includes("critical_actionability_below_3"));
});

test("frozen threshold boundaries are executable without rounding", async () => {
  const thresholds = JSON.parse(await readFile(path.join(evalRoot, "thresholds.json"), "utf8"));
  assert.equal(assessThreshold(0.95, thresholds.metrics.requirement_recall), "target");
  assert.equal(assessThreshold(0.90, thresholds.metrics.requirement_recall), "minimum_acceptable");
  assert.equal(assessThreshold(0.79, thresholds.metrics.requirement_recall), "release_blocker");
  assert.equal(assessThreshold(0.05, thresholds.metrics.unsupported_output_rate), "target");
  assert.equal(assessThreshold(0.10, thresholds.metrics.unsupported_output_rate), "minimum_acceptable");
  assert.equal(assessThreshold(0.16, thresholds.metrics.unsupported_output_rate), "release_blocker");
  assert.equal(assessThreshold(0, thresholds.metrics.critical_omission_rate), "target");
  assert.equal(assessThreshold(0.01, thresholds.metrics.critical_omission_rate), "release_blocker");
});

test("reports and evaluator never expose prohibited evaluation content", async () => {
  const report = await runEvaluation({ root: evalRoot });
  const serialized = JSON.stringify(report);
  for (const prohibited of [
    "canonical_text", "context_items", "expected_output", "source_refs", "raw_provider_response",
    "prompt", "reviewer_free_text_notes", "کافه", "سریع‌ترین تجربه بازار", "رزرو میز"
  ]) assert.doesNotMatch(serialized, new RegExp(prohibited, "iu"));
});

test("real Provider execution remains blocked until G02/G03", async () => {
  await assert.rejects(() => runEvaluation({ root: evalRoot, provider: { mode: "real_provider", execute: async () => ({ requirements: [] }) } }), /deferred to G02\/G03/);
});

test("ADR-034 freezes item blockers, human N/A and Eval-only critical annotation", async () => {
  const adr = await readFile(path.join(root, "docs/adr/ADR-034-requirement-evaluation-contract.md"), "utf8");
  assert.match(adr, /Status:\*\* Accepted/);
  assert.match(adr, /Any unmatched `critical_for_scope` Gold Requirement is a Release Blocker/);
  assert.match(adr, /With\s+`N_generated=0`, both are `N\/A`/);
  assert.match(adr, /never enters the Requirement Domain, database or public API/);
});
