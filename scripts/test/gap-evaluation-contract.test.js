import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import {
  GAP_TYPES,
  FakeDeterministicProvider,
  assessThreshold,
  calculateHumanReview,
  evaluateOutput,
  loadFixtures,
  runEvaluation,
  validateFixtureContract
} from "../gap-evaluation.mjs";

const root = process.cwd();
const evalRoot = path.join(root, "evals/gap-detection/gap_detection_eval_v1");

test("J05 contains exactly twenty immutable Persian synthetic fixtures", async () => {
  const manifest = JSON.parse(await readFile(path.join(evalRoot, "manifest.json"), "utf8"));
  const fixtures = await loadFixtures(evalRoot);
  assert.equal(manifest.eval_set_id, "gap_detection_eval_v1");
  assert.equal(manifest.expected_fixture_count, 20);
  assert.deepEqual(fixtures.map((fixture) => fixture.fixture_id), manifest.fixture_ids);
  assert.deepEqual([...new Set(fixtures.map((fixture) => fixture.project_type))].sort(), ["corporate", "landing", "portfolio"]);
  assert.deepEqual([...new Set(fixtures.flatMap((fixture) => fixture.expected_output.gaps.map((gap) => gap.gap_type)))].sort(), [...GAP_TYPES].sort());
  assert.ok(fixtures.some((fixture) => fixture.expected_output.no_gap));
});

test("source_refs_expectation is executable and provenance remains tenant/source bounded", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const fixture = fixtures.find((item) => item.expected_output.gaps[0]?.source_refs_expectation === "required");
  const output = await new FakeDeterministicProvider().execute(fixture);
  const result = evaluateOutput(fixture, output);
  assert.deepEqual(result.failure_categories, []);
  assert.equal(fixture.expected_output.gaps[0].source_refs_expectation, "required");
  const invalid = structuredClone(fixture);
  invalid.expected_output.gaps[0].source_refs_expectation = "empty";
  assert.throws(() => validateFixtureContract(invalid), /gold_required_source_refs|gold_empty_source_refs/);
});

test("Fake Provider passes only the contract harness and never claims model quality", async () => {
  const report = await runEvaluation({ root: evalRoot, provider: new FakeDeterministicProvider() });
  assert.equal(report.fixture_count, 20);
  assert.equal(report.contract_gate.status, "pass");
  assert.deepEqual(report.model_quality_gate, { status: "not_run", reason: "real_provider_and_human_review_required" });
  assert.equal(report.metrics.gap_recall.value, 1);
  assert.equal(report.metrics.critical_gap_recall.value, 1);
  assert.equal(report.metrics.false_gap_rate.value, 0);
  assert.equal(report.metrics.critical_gap_precision.value, 1);
  assert.equal(report.metrics.semantic_validity_score.value, null);
});

test("critical recall and critical precision are distinct metrics", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const target = fixtures.find((fixture) => fixture.expected_output.gaps.some((gap) => gap.critical_for_scope));
  const provider = { mode: "fake_deterministic", async execute(fixture) {
    const output = await new FakeDeterministicProvider().execute(fixture);
    return fixture.fixture_id === target.fixture_id ? { gaps: [] } : output;
  }};
  const report = await runEvaluation({ root: evalRoot, provider });
  assert.equal(report.metrics.critical_gap_recall.value < 1, true);
  assert.ok(report.critical_blockers.includes("critical_gold_unmatched"));
});

test("critical output without Rule Pack authority is a contract failure", async () => {
  const [fixture] = await loadFixtures(evalRoot);
  const output = await new FakeDeterministicProvider().execute(fixture);
  if (output.gaps.length === 0) return;
  output.gaps[0].severity = "critical";
  output.gaps[0].critical_rule_id = null;
  const result = evaluateOutput(fixture, output);
  assert.ok(result.failure_categories.includes("critical_rule_mismatch"));
});

test("false gap rate detects an unmatched generated gap and no-gap fixtures", async () => {
  const fixtures = await loadFixtures(evalRoot);
  const target = fixtures.find((fixture) => fixture.expected_output.no_gap);
  const provider = { mode: "fake_deterministic", async execute(fixture) {
    if (fixture.fixture_id === target.fixture_id) return { gaps: [{ candidate_id: `${fixture.fixture_id}_false`, gap_type: "ambiguity", severity: "medium", source_refs: [], affected_requirement_ids: [], critical_rule_id: null }] };
    return new FakeDeterministicProvider().execute(fixture);
  }};
  const report = await runEvaluation({ root: evalRoot, provider });
  assert.ok(report.metrics.false_gap_rate.value > 0);
});

test("human review requires adjudication for a difference of two and blocks low semantic quality", () => {
  const pending = calculateHumanReview({
    generatedCandidateIds: ["candidate-1"],
    records: [{ candidate_id: "candidate-1", reviewers: [
      { reviewer_id: "reviewer-1", semantic_validity_score: 2 },
      { reviewer_id: "reviewer-2", semantic_validity_score: 4 }
    ] }]
  });
  assert.equal(pending.status, "adjudication_required");
  const scored = calculateHumanReview({
    generatedCandidateIds: ["candidate-1"],
    criticalCandidateIds: ["candidate-1"],
    records: [{ candidate_id: "candidate-1", reviewers: [
      { reviewer_id: "reviewer-1", semantic_validity_score: 2 },
      { reviewer_id: "reviewer-2", semantic_validity_score: 2 }
    ], adjudication: undefined }]
  });
  assert.equal(scored.semantic_validity_score.value, 2);
  assert.equal(scored.critical_semantic_below_3, true);
});

test("frozen threshold boundaries and N/A semantics are executable", async () => {
  const thresholds = JSON.parse(await readFile(path.join(evalRoot, "thresholds.json"), "utf8"));
  assert.equal(assessThreshold(1, thresholds.metrics.critical_gap_recall), "target");
  assert.equal(assessThreshold(0.99, thresholds.metrics.critical_gap_recall), "release_blocker");
  assert.equal(assessThreshold(0.95, thresholds.metrics.gap_recall), "target");
  assert.equal(assessThreshold(0.21, thresholds.metrics.false_gap_rate), "release_blocker");
  assert.equal(assessThreshold(4.5, thresholds.metrics.semantic_validity_score), "target");
  const noOutput = calculateHumanReview({ generatedCandidateIds: [], records: [] });
  assert.equal(noOutput.semantic_validity_score.value, null);
});

test("reports never expose fixture content, source references, raw provider data or reviewer notes", async () => {
  const report = await runEvaluation({ root: evalRoot });
  const serialized = JSON.stringify(report);
  for (const prohibited of ["context_items", "requirement", "source_refs", "raw_provider_response", "prompt", "reviewer_free_text", "محدوده پروژه"]) assert.doesNotMatch(serialized, new RegExp(prohibited, "iu"));
});

test("real Provider quality execution remains deferred to G02/G03", async () => {
  await assert.rejects(() => runEvaluation({ root: evalRoot, provider: { mode: "real_provider", execute: async () => ({ gaps: [] }) } }), /deferred to G02\/G03/);
});

test("ADR-040 freezes J05 metric and provider boundaries", async () => {
  const adr = await readFile(path.join(root, "docs/adr/ADR-040-gap-evaluation-contract.md"), "utf8");
  assert.match(adr, /Status:\*\* Accepted/);
  assert.match(adr, /critical_gap_recall/);
  assert.match(adr, /critical_gap_rule_pack_v1/);
  assert.match(adr, /Real Provider.*G02\/G03/iu);
});
