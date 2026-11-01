import assert from "node:assert/strict";
import test from "node:test";

import { loadFixtures as loadContextFixtures } from "../context-evaluation.mjs";
import { loadFixtures as loadRequirementFixtures } from "../requirement-evaluation.mjs";
import { loadFixtures as loadGapFixtures } from "../gap-evaluation.mjs";
import {
  REVIEW_IMPORT_VERSION,
  buildProviderQualityComparison,
  percentileNearestRank
} from "../provider-quality-comparison.mjs";

const candidates = [
  ["openai", "gpt-5.6-terra"],
  ["google", "gemini-3.8-flash"]
];

function reviewer(reviewerId, scores) {
  return { reviewer_id: reviewerId, scores };
}

function contextCase(fixture, provider, model, index) {
  const items = fixture.expected_structured_output.items.map((gold, itemIndex) => ({
    candidate_id: `${fixture.fixture_id}_candidate_${String(itemIndex + 1).padStart(3, "0")}`,
    item_type: gold.item_type,
    content: gold.content,
    source_refs: gold.source_refs.map((ref) => ({ ...ref, start_offset: null, end_offset: null })),
    confidence: "1",
    rationale_short: null
  }));
  const dimensions = {
    semantic_correctness: 5,
    persian_quality: 5,
    no_hallucination: 5,
    attribution_provenance: 5,
    usefulness: 5,
    client_intent_preservation: 5
  };
  return pair(
    fixture,
    provider,
    model,
    index,
    { items },
    items.map((item, itemIndex) => alignment(item.candidate_id, fixture.expected_structured_output.items[itemIndex].gold_item_id)),
    {
      reviewers: [reviewer("reviewer-a", dimensions), reviewer("reviewer-b", dimensions)],
      adjudication: null
    },
    []
  );
}

function requirementCase(fixture, provider, model, index) {
  const items = fixture.expected_output.requirements.map((gold, itemIndex) => ({
    candidate_id: `${fixture.fixture_id}_candidate_${String(itemIndex + 1).padStart(3, "0")}`,
    title: gold.title,
    description: gold.description,
    category: gold.category,
    priority: gold.priority,
    source_refs: gold.source_refs.map((ref) => ({ ...ref, start_offset: null, end_offset: null })),
    confidence: "1",
    unsupported: gold.is_unsupported,
    duplicate_group_key: null,
    conflict_group_key: null
  }));
  const reviews = items.map((item) => ({
    candidate_id: item.candidate_id,
    reviewers: [
      reviewer("reviewer-a", { clarity_score: 5, actionability_score: 5 }),
      reviewer("reviewer-b", { clarity_score: 5, actionability_score: 5 })
    ],
    adjudication: null
  }));
  return pair(
    fixture,
    provider,
    model,
    index,
    { items },
    items.map((item, itemIndex) => alignment(item.candidate_id, fixture.expected_output.requirements[itemIndex].gold_requirement_id, fixture.expected_output.requirements[itemIndex].is_unsupported)),
    null,
    reviews
  );
}

function gapCase(fixture, provider, model, index) {
  const items = fixture.expected_output.gaps.map((gold, itemIndex) => ({
    candidate_id: `${fixture.fixture_id}_candidate_${String(itemIndex + 1).padStart(3, "0")}`,
    gap_type: gold.gap_type,
    severity: gold.severity,
    explanation: "synthetic review fixture",
    source_refs: gold.source_refs,
    affected_requirement_ids: gold.affected_requirement_ids,
    suggested_resolution_type: resolution(gold.gap_type),
    critical_rule_id: gold.critical_rule_id
  }));
  const reviews = items.map((item) => ({
    candidate_id: item.candidate_id,
    reviewers: [
      reviewer("reviewer-a", { semantic_validity_score: 5 }),
      reviewer("reviewer-b", { semantic_validity_score: 5 })
    ],
    adjudication: null
  }));
  return pair(
    fixture,
    provider,
    model,
    index,
    { items, matched_critical_rule_ids: fixture.expected_output.gaps.map((item) => item.critical_rule_id).filter(Boolean) },
    items.map((item, itemIndex) => alignment(item.candidate_id, fixture.expected_output.gaps[itemIndex].gold_gap_id)),
    null,
    reviews
  );
}

function pair(fixture, provider, model, index, normalizedOutput, alignments, fixtureReview, candidateReviews) {
  const suite = fixture.eval_set_id;
  return {
    result: {
      fixture_id: fixture.fixture_id,
      eval_suite_version: suite,
      provider,
      model,
      status: "succeeded",
      failure_class: null,
      estimated_cost: "0.10000000",
      input_tokens: 10,
      cached_input_tokens: 2,
      output_tokens: 5,
      latency_ms: index + 1,
      normalized_output: normalizedOutput
    },
    review: {
      provider,
      model,
      fixture_id: fixture.fixture_id,
      eval_suite_version: suite,
      alignments,
      fixture_review: fixtureReview,
      candidate_reviews: candidateReviews
    }
  };
}

function alignment(candidateId, goldId, unsupported = false) {
  return {
    candidate_id: candidateId,
    matched_gold_id: goldId,
    semantically_unsupported: unsupported,
    duplicate_group_id: null
  };
}

function resolution(type) {
  return {
    missing_information: "provide_information",
    ambiguity: "clarify_ambiguity",
    conflict: "resolve_conflict",
    decision_required: "make_decision",
    unsupported_assumption: "validate_assumption",
    scope_risk: "mitigate_scope_risk"
  }[type];
}

async function completeEvidence() {
  const [context, requirements, gaps] = await Promise.all([
    loadContextFixtures(),
    loadRequirementFixtures(),
    loadGapFixtures()
  ]);
  const pairs = [];
  for (const [provider, model] of candidates) {
    context.forEach((fixture, index) => pairs.push(contextCase(fixture, provider, model, index)));
    requirements.forEach((fixture, index) => pairs.push(requirementCase(fixture, provider, model, index + 20)));
    gaps.forEach((fixture, index) => pairs.push(gapCase(fixture, provider, model, index + 40)));
  }
  return {
    run: { execution_manifest_hash: "manifest-0086", cases: pairs.map((item) => item.result) },
    review: {
      review_version: REVIEW_IMPORT_VERSION,
      execution_manifest_hash: "manifest-0086",
      cases: pairs.map((item) => item.review)
    }
  };
}

test("0086 imports complete adjudicated evidence into a content-free comparison report", async () => {
  const evidence = await completeEvidence();
  const report = await buildProviderQualityComparison(evidence);

  assert.equal(report.candidates.length, 2);
  for (const candidate of report.candidates) {
    assert.deepEqual(candidate.operations.latency_ms, { sample_count: 60, p50: 30, p95: 57, max: 60 });
    assert.equal(candidate.operations.cost.total, "6.00000000");
    assert.equal(candidate.operations.cost.average, "0.10000000");
    assert.equal(
      candidate.quality.context.contract_gate,
      "pass",
      JSON.stringify(candidate.quality.context.fixtures.filter((item) => item.failure_categories.length > 0))
    );
    assert.equal(candidate.quality.requirements.contract_gate, "pass");
    assert.equal(candidate.quality.gaps.contract_gate, "pass");
    assert.equal(candidate.quality.requirements.human_review_status, "scored");
    assert.equal(candidate.quality.gaps.human_review_status, "scored");
  }
  const serialized = JSON.stringify(report);
  for (const forbidden of ["content", "title", "description", "source_refs", "synthetic review fixture"]) {
    assert.equal(serialized.includes(forbidden), false);
  }
});

test("0086 review import rejects free-text or unapproved fields", async () => {
  const evidence = await completeEvidence();
  evidence.review.cases[0].notes = "must never enter the report";

  await assert.rejects(() => buildProviderQualityComparison(evidence), /INVALID_REVIEW_CASE/);
});

test("nearest-rank latency is deterministic and N/A-safe", () => {
  assert.equal(percentileNearestRank([], 0.95), null);
  assert.equal(percentileNearestRank([1, 2, 3, 4], 0.5), 2);
  assert.equal(percentileNearestRank([1, 2, 3, 4], 0.95), 4);
});
