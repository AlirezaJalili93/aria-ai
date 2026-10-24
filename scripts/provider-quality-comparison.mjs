import { readFile } from "node:fs/promises";
import path from "node:path";

import {
  CLASS_NAMES,
  assessThreshold as assessContextThreshold,
  calculateClassification,
  calculatePersianQuality,
  evaluateOutput as evaluateContextOutput,
  loadFixtures as loadContextFixtures
} from "./context-evaluation.mjs";
import {
  assessThreshold as assessRequirementThreshold,
  calculateHumanReview as calculateRequirementReview,
  evaluateOutput as evaluateRequirementOutput,
  loadFixtures as loadRequirementFixtures
} from "./requirement-evaluation.mjs";
import {
  assessThreshold as assessGapThreshold,
  calculateHumanReview as calculateGapReview,
  evaluateOutput as evaluateGapOutput,
  loadFixtures as loadGapFixtures
} from "./gap-evaluation.mjs";

export const REVIEW_IMPORT_VERSION = "provider-quality-human-review-v1";

const roots = {
  context: path.resolve("evals/context-structuring/context_structuring_eval_v1"),
  requirement: path.resolve("evals/requirement-extraction/requirement_extraction_eval_v1"),
  gap: path.resolve("evals/gap-detection/gap_detection_eval_v1")
};

const metric = (numerator, denominator) => ({
  value: denominator === 0 ? null : numerator / denominator,
  numerator,
  denominator
});

export async function buildProviderQualityComparison({ run, review }) {
  validateTopLevel(run, review);
  const [contextFixtures, requirementFixtures, gapFixtures, thresholds] = await Promise.all([
    loadContextFixtures(),
    loadRequirementFixtures(),
    loadGapFixtures(),
    loadThresholds()
  ]);
  const fixtures = {
    context_structuring_eval_v1: new Map(contextFixtures.map((item) => [item.fixture_id, item])),
    requirement_extraction_eval_v1: new Map(requirementFixtures.map((item) => [item.fixture_id, item])),
    gap_detection_eval_v1: new Map(gapFixtures.map((item) => [item.fixture_id, item]))
  };
  const reviews = reviewIndex(review.cases);
  const candidateGroups = groupCases(run.cases);
  if (candidateGroups.size !== 2 || [...candidateGroups.values()].some((values) => values.length !== 60)) throw new Error("EVALUATION_MATRIX_INCOMPLETE");
  const candidates = [];
  for (const [identity, cases] of candidateGroups) {
    const [provider, model] = identity.split("\u0000");
    const reviewCases = cases.map((result) => {
      const fixture = fixtures[result.eval_suite_version]?.get(result.fixture_id);
      if (!fixture) throw new Error("UNKNOWN_EVALUATION_FIXTURE");
      const key = reviewKey(provider, model, result.eval_suite_version, result.fixture_id);
      const caseReview = reviews.get(key);
      if (result.status === "succeeded" && !caseReview) throw new Error("MISSING_HUMAN_REVIEW_CASE");
      if (result.status !== "succeeded" && caseReview) throw new Error("REVIEW_FOR_FAILED_CASE_PROHIBITED");
      return { result, fixture, review: caseReview };
    });
    candidates.push({
      provider,
      model,
      operations: operationalSummary(cases),
      quality: {
        context: contextReport(reviewCases, thresholds.context),
        requirements: requirementReport(reviewCases, thresholds.requirement),
        gaps: gapReport(reviewCases, thresholds.gap)
      }
    });
  }
  if (reviews.size !== [...candidateGroups.values()].flat().filter((item) => item.status === "succeeded").length) {
    throw new Error("HUMAN_REVIEW_INVENTORY_MISMATCH");
  }
  return {
    report_version: "provider-quality-comparison-v1",
    execution_manifest_hash: run.execution_manifest_hash,
    review_version: review.review_version,
    quality_gate: "evidence_only_no_automatic_promotion",
    candidates
  };
}

function contextReport(cases, thresholds) {
  const evaluated = [];
  const finalPersianScores = [];
  let humanPassed = 0;
  for (const entry of cases.filter((item) => item.result.eval_suite_version === "context_structuring_eval_v1")) {
    if (entry.result.status !== "succeeded") {
      evaluated.push(evaluateContextOutput(entry.fixture, { items: [], failure: { code: entry.result.failure_class }, repair_attempted: false }));
      continue;
    }
    const items = normalizedItems(entry.result);
    const alignments = validateAlignments(entry.review, items, entry.fixture.expected_structured_output.items.map((item) => item.gold_item_id));
    const byCandidate = new Map(alignments.map((item) => [item.candidate_id, item]));
    const output = {
      items: items.map((item) => ({
        item_id: byCandidate.get(item.candidate_id).matched_gold_id ?? `unmatched:${item.candidate_id}`,
        item_type: item.item_type,
        content: item.content,
        source_refs: item.source_refs
      })),
      failure: (
        entry.fixture.failure_expectations.expected_outcome === "fail" && items.length === 0
          ? { code: entry.fixture.failure_expectations.allowed_failure_codes[0] }
          : null
      ),
      repair_attempted: false
    };
    const result = evaluateContextOutput(entry.fixture, output);
    const assumptions = items.filter((item) => item.item_type === "assumption");
    result.unsupported_assumptions = {
      predicted: assumptions.length,
      unsupported: assumptions.filter((item) => byCandidate.get(item.candidate_id).semantically_unsupported).length
    };
    evaluated.push(result);
    const reviewResult = resolveContextFixtureReview(entry.review.fixture_review);
    finalPersianScores.push(reviewResult.scores.persian_quality);
    if (reviewResult.passed) humanPassed += 1;
  }
  const eligible = sum(evaluated, (item) => item.source_trace.eligible);
  const traced = sum(evaluated, (item) => item.source_trace.valid);
  const assumptions = sum(evaluated, (item) => item.unsupported_assumptions.predicted);
  const unsupported = sum(evaluated, (item) => item.unsupported_assumptions.unsupported);
  const classification = aggregateClassification(evaluated.map((item) => item.classification));
  const firstPass = evaluated.filter((item) => item.first_pass_valid).length;
  const jsonValid = evaluated.filter((item) => item.json_valid).length;
  const persian = calculatePersianQuality(finalPersianScores);
  const metrics = {
    source_trace_rate: metric(traced, eligible),
    unsupported_assumption_rate: metric(unsupported, assumptions),
    persian_quality: persian,
    classification,
    first_pass_valid_rate: metric(firstPass, evaluated.length),
    json_validity_after_repair: metric(jsonValid, evaluated.length),
    human_fixture_pass_rate: metric(humanPassed, evaluated.length)
  };
  return {
    metrics,
    threshold_assessments: {
      source_trace_rate: assessContextThreshold(metrics.source_trace_rate.value, thresholds.metrics.source_trace_rate),
      unsupported_assumption_rate: assessContextThreshold(metrics.unsupported_assumption_rate.value, thresholds.metrics.unsupported_assumption_rate),
      persian_quality_raw_mean: assessContextThreshold(finalPersianScores.length === 0 ? null : sum(finalPersianScores, (value) => value) / finalPersianScores.length, thresholds.metrics.persian_quality_raw_mean),
      classification_macro_f1: assessContextThreshold(classification.macro_f1, thresholds.metrics.classification_macro_f1),
      first_pass_valid_rate: assessContextThreshold(metrics.first_pass_valid_rate.value, thresholds.metrics.first_pass_valid_rate),
      json_validity_after_repair: assessContextThreshold(metrics.json_validity_after_repair.value, thresholds.metrics.json_validity_after_repair)
    },
    contract_gate: evaluated.every((item) => item.failure_categories.length === 0) ? "pass" : "fail",
    fixtures: safeFixtureResults(evaluated)
  };
}

function requirementReport(cases, thresholds) {
  const evaluated = [];
  const reviewRecords = [];
  for (const entry of cases.filter((item) => item.result.eval_suite_version === "requirement_extraction_eval_v1")) {
    if (entry.result.status !== "succeeded") {
      evaluated.push(emptyRequirementEvaluation(entry.fixture, entry.result.failure_class));
      continue;
    }
    const items = normalizedItems(entry.result);
    const gold = entry.fixture.expected_output.requirements;
    const alignments = validateAlignments(entry.review, items, gold.map((item) => item.gold_requirement_id));
    const dynamicFixture = withRequirementAnnotations(entry.fixture, alignments, gold);
    const output = {
      requirements: items.map((item) => ({
        candidate_id: item.candidate_id,
        title: item.title,
        description: item.description,
        category: item.category,
        priority: item.priority,
        source_refs: item.source_refs,
        is_unsupported: item.unsupported
      }))
    };
    evaluated.push(evaluateRequirementOutput(dynamicFixture, output));
    reviewRecords.push(...requirementReviewRecords(entry.review, items));
  }
  const totals = totalCounts(evaluated, ["gold", "matched_gold", "critical_gold", "omitted_critical", "generated", "unsupported", "detected_unsupported", "duplicate_extras", "critical_unsupported_misses"]);
  const generatedIds = evaluated.flatMap((item) => item.generated_candidate_ids);
  const criticalIds = evaluated.flatMap((item) => item.critical_candidate_ids);
  const human = calculateRequirementReview({ generatedCandidateIds: generatedIds, criticalCandidateIds: criticalIds, records: reviewRecords });
  const metrics = {
    requirement_recall: metric(totals.matched_gold, totals.gold),
    critical_omission_rate: metric(totals.omitted_critical, totals.critical_gold),
    unsupported_output_rate: metric(totals.unsupported, totals.generated),
    unsupported_detection_rate: metric(totals.detected_unsupported, totals.unsupported),
    duplicate_rate: metric(totals.duplicate_extras, totals.generated),
    clarity_score: human.clarity_score,
    actionability_score: human.actionability_score
  };
  const blockers = [];
  if (totals.omitted_critical > 0) blockers.push("critical_gold_unmatched");
  if (totals.critical_unsupported_misses > 0) blockers.push("critical_unsupported_not_detected");
  if (human.critical_clarity_below_3) blockers.push("critical_clarity_below_3");
  if (human.critical_actionability_below_3) blockers.push("critical_actionability_below_3");
  return {
    metrics,
    threshold_assessments: Object.fromEntries(Object.entries(metrics).map(([name, value]) => [name, assessRequirementThreshold(value.value, thresholds.metrics[name])])),
    critical_blockers: blockers,
    human_review_status: human.status,
    contract_gate: evaluated.every((item) => item.failure_categories.length === 0) ? "pass" : "fail",
    fixtures: safeFixtureResults(evaluated)
  };
}

function gapReport(cases, thresholds) {
  const evaluated = [];
  const reviewRecords = [];
  for (const entry of cases.filter((item) => item.result.eval_suite_version === "gap_detection_eval_v1")) {
    if (entry.result.status !== "succeeded") {
      evaluated.push(emptyGapEvaluation(entry.fixture, entry.result.failure_class));
      continue;
    }
    const items = normalizedItems(entry.result);
    const gold = entry.fixture.expected_output.gaps;
    const alignments = validateAlignments(entry.review, items, gold.map((item) => item.gold_gap_id));
    const dynamicFixture = withGapAnnotations(entry.fixture, alignments, gold);
    const output = { gaps: items.map((item) => ({ ...item })) };
    evaluated.push(evaluateGapOutput(dynamicFixture, output));
    reviewRecords.push(...gapReviewRecords(entry.review, items));
  }
  const totals = totalCounts(evaluated, ["gold", "matched_gold", "critical_gold", "matched_critical", "omitted_critical", "generated", "false_gaps", "authoritative_critical", "correct_critical", "duplicate_extras"]);
  const generatedIds = evaluated.flatMap((item) => item.generated_candidate_ids);
  const criticalIds = evaluated.flatMap((item) => item.critical_candidate_ids);
  const human = calculateGapReview({ generatedCandidateIds: generatedIds, criticalCandidateIds: criticalIds, records: reviewRecords });
  const metrics = {
    gap_recall: metric(totals.matched_gold, totals.gold),
    critical_gap_recall: metric(totals.matched_critical, totals.critical_gold),
    false_gap_rate: metric(totals.false_gaps, totals.generated),
    critical_gap_precision: metric(totals.correct_critical, totals.authoritative_critical),
    semantic_validity_score: human.semantic_validity_score
  };
  const blockers = [];
  if (totals.omitted_critical > 0) blockers.push("critical_gold_unmatched");
  if (totals.duplicate_extras > 0) blockers.push("duplicate_gap");
  if (evaluated.some((item) => item.failure_categories.includes("critical_rule_mismatch"))) blockers.push("critical_rule_mismatch");
  if (human.critical_semantic_below_3) blockers.push("critical_semantic_below_3");
  return {
    metrics,
    threshold_assessments: Object.fromEntries(Object.entries(metrics).map(([name, value]) => [name, assessGapThreshold(value.value, thresholds.metrics[name])])),
    critical_blockers: blockers,
    human_review_status: human.status,
    contract_gate: evaluated.every((item) => item.failure_categories.length === 0) ? "pass" : "fail",
    fixtures: safeFixtureResults(evaluated)
  };
}

function validateTopLevel(run, review) {
  if (!run || typeof run !== "object" || !Array.isArray(run.cases) || typeof run.execution_manifest_hash !== "string") throw new Error("INVALID_EVALUATION_RUN");
  if (!review || review.review_version !== REVIEW_IMPORT_VERSION || review.execution_manifest_hash !== run.execution_manifest_hash || !Array.isArray(review.cases)) throw new Error("INVALID_HUMAN_REVIEW_IMPORT");
}

function reviewIndex(values) {
  const result = new Map();
  for (const value of values) {
    assertExactKeys(value, ["provider", "model", "fixture_id", "eval_suite_version", "alignments", "fixture_review", "candidate_reviews"], "review case");
    const key = reviewKey(value.provider, value.model, value.eval_suite_version, value.fixture_id);
    if (result.has(key)) throw new Error("DUPLICATE_HUMAN_REVIEW_CASE");
    result.set(key, value);
  }
  return result;
}

function validateAlignments(caseReview, items, goldIds) {
  if (!Array.isArray(caseReview.alignments) || caseReview.alignments.length !== items.length) throw new Error("ALIGNMENT_INVENTORY_MISMATCH");
  const itemIds = new Set(items.map((item) => item.candidate_id));
  const allowedGold = new Set(goldIds);
  const matchedGold = new Set();
  const seen = new Set();
  for (const alignment of caseReview.alignments) {
    assertExactKeys(alignment, ["candidate_id", "matched_gold_id", "semantically_unsupported", "duplicate_group_id"], "alignment");
    if (!itemIds.has(alignment.candidate_id) || seen.has(alignment.candidate_id) || typeof alignment.semantically_unsupported !== "boolean") throw new Error("INVALID_ALIGNMENT");
    seen.add(alignment.candidate_id);
    if (alignment.matched_gold_id !== null) {
      if (!allowedGold.has(alignment.matched_gold_id) || matchedGold.has(alignment.matched_gold_id)) throw new Error("INVALID_ONE_TO_ONE_ALIGNMENT");
      matchedGold.add(alignment.matched_gold_id);
    }
    if (alignment.duplicate_group_id !== null && (typeof alignment.duplicate_group_id !== "string" || !alignment.duplicate_group_id)) throw new Error("INVALID_DUPLICATE_GROUP");
  }
  return caseReview.alignments;
}

function resolveContextFixtureReview(value) {
  if (!value) throw new Error("CONTEXT_FIXTURE_REVIEW_REQUIRED");
  const dimensions = ["semantic_correctness", "persian_quality", "no_hallucination", "attribution_provenance", "usefulness", "client_intent_preservation"];
  assertExactKeys(value, ["reviewers", "adjudication"], "context fixture review");
  const scores = resolveScores(value, dimensions, 1, false);
  const mean = sum(Object.values(scores), (item) => item) / dimensions.length;
  const passed = mean >= 4 && scores.no_hallucination >= 4 && scores.attribution_provenance >= 4 && scores.client_intent_preservation >= 4;
  return { scores, passed };
}

function requirementReviewRecords(caseReview, items) {
  if (caseReview.fixture_review !== null || !Array.isArray(caseReview.candidate_reviews)) throw new Error("INVALID_REQUIREMENT_REVIEW_SHAPE");
  const reviews = new Map(caseReview.candidate_reviews.map((item) => [item.candidate_id, item]));
  if (reviews.size !== items.length) throw new Error("REQUIREMENT_REVIEW_INVENTORY_MISMATCH");
  return items.map((item) => {
    const record = reviews.get(item.candidate_id);
    if (!record) throw new Error("MISSING_REQUIREMENT_REVIEW");
    return scoreRecord(record, ["clarity_score", "actionability_score"]);
  });
}

function gapReviewRecords(caseReview, items) {
  if (caseReview.fixture_review !== null || !Array.isArray(caseReview.candidate_reviews)) throw new Error("INVALID_GAP_REVIEW_SHAPE");
  const reviews = new Map(caseReview.candidate_reviews.map((item) => [item.candidate_id, item]));
  if (reviews.size !== items.length) throw new Error("GAP_REVIEW_INVENTORY_MISMATCH");
  return items.map((item) => {
    const record = reviews.get(item.candidate_id);
    if (!record) throw new Error("MISSING_GAP_REVIEW");
    return scoreRecord(record, ["semantic_validity_score"]);
  });
}

function scoreRecord(record, dimensions) {
  assertExactKeys(record, ["candidate_id", "reviewers", "adjudication"], "candidate review");
  if (!Array.isArray(record.reviewers) || record.reviewers.length !== 2) throw new Error("EXACTLY_TWO_REVIEWERS_REQUIRED");
  const reviewers = record.reviewers.map((reviewer) => {
    assertExactKeys(reviewer, ["reviewer_id", "scores"], "reviewer");
    return { reviewer_id: reviewer.reviewer_id, ...reviewer.scores };
  });
  if (reviewers[0].reviewer_id === reviewers[1].reviewer_id) throw new Error("INDEPENDENT_REVIEWERS_REQUIRED");
  const result = { candidate_id: record.candidate_id, reviewers };
  if (record.adjudication !== null) result.adjudication = record.adjudication;
  for (const reviewer of reviewers) validateScoreKeys(reviewer, dimensions);
  if (result.adjudication) validateScoreKeys(result.adjudication, dimensions, false);
  return result;
}

function resolveScores(value, dimensions, disagreementLimit, candidateRecord = true) {
  const record = candidateRecord ? scoreRecord(value, dimensions) : fixtureScoreRecord(value, dimensions);
  const scores = {};
  for (const dimension of dimensions) {
    const first = record.reviewers[0][dimension];
    const second = record.reviewers[1][dimension];
    const adjudicated = record.adjudication?.[dimension];
    if (Math.abs(first - second) > disagreementLimit || (first >= 4) !== (second >= 4)) {
      if (!validScore(adjudicated)) throw new Error("ADJUDICATION_REQUIRED");
      scores[dimension] = adjudicated;
    } else scores[dimension] = (first + second) / 2;
  }
  return scores;
}

function fixtureScoreRecord(value, dimensions) {
  if (!Array.isArray(value.reviewers) || value.reviewers.length !== 2) throw new Error("EXACTLY_TWO_REVIEWERS_REQUIRED");
  const reviewers = value.reviewers.map((reviewer) => {
    assertExactKeys(reviewer, ["reviewer_id", "scores"], "reviewer");
    const resolved = { reviewer_id: reviewer.reviewer_id, ...reviewer.scores };
    validateScoreKeys(resolved, dimensions);
    return resolved;
  });
  if (reviewers[0].reviewer_id === reviewers[1].reviewer_id) throw new Error("INDEPENDENT_REVIEWERS_REQUIRED");
  const result = { reviewers };
  if (value.adjudication !== null) {
    validateScoreKeys(value.adjudication, dimensions, false);
    result.adjudication = value.adjudication;
  }
  return result;
}

function withRequirementAnnotations(fixture, alignments, gold) {
  const goldById = new Map(gold.map((item) => [item.gold_requirement_id, item]));
  return {
    ...fixture,
    evaluation_annotations: {
      candidate_annotations: alignments.map((item) => ({
        candidate_id: item.candidate_id,
        gold_requirement_id: item.matched_gold_id,
        semantically_unsupported: item.semantically_unsupported,
        critical_for_scope: item.matched_gold_id === null ? false : goldById.get(item.matched_gold_id).critical_for_scope
      })),
      deterministic_output_candidate_ids: alignments.map((item) => item.candidate_id),
      semantic_duplicate_groups: duplicateGroups(alignments)
    }
  };
}

function withGapAnnotations(fixture, alignments, gold) {
  const goldById = new Map(gold.map((item) => [item.gold_gap_id, item]));
  return {
    ...fixture,
    evaluation_annotations: {
      candidate_annotations: alignments.map((item) => {
        const matched = item.matched_gold_id === null ? null : goldById.get(item.matched_gold_id);
        return {
          candidate_id: item.candidate_id,
          gold_gap_id: item.matched_gold_id,
          semantically_unsupported: item.semantically_unsupported,
          critical_for_scope: matched?.critical_for_scope ?? false,
          source_refs_expectation: matched?.source_refs_expectation ?? "optional"
        };
      }),
      deterministic_output_candidate_ids: alignments.map((item) => item.candidate_id),
      semantic_duplicate_groups: duplicateGroups(alignments)
    }
  };
}

function duplicateGroups(alignments) {
  const groups = new Map();
  for (const item of alignments) {
    if (item.duplicate_group_id === null) continue;
    const values = groups.get(item.duplicate_group_id) ?? [];
    values.push(item.candidate_id);
    groups.set(item.duplicate_group_id, values);
  }
  return [...groups].map(([group_id, candidate_ids]) => ({ group_id, candidate_ids }));
}

function normalizedItems(result) {
  const items = result.normalized_output?.items;
  if (!Array.isArray(items)) throw new Error("NORMALIZED_OUTPUT_REQUIRED");
  return items;
}

function groupCases(cases) {
  const result = new Map();
  for (const item of cases) {
    const key = `${item.provider}\u0000${item.model}`;
    const values = result.get(key) ?? [];
    values.push(item);
    result.set(key, values);
  }
  return result;
}

function operationalSummary(cases) {
  const latencies = cases.map((item) => item.latency_ms).filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  const costs = cases.map((item) => item.estimated_cost).filter((value) => value !== null && value !== undefined);
  const failures = {};
  for (const item of cases) if (item.status !== "succeeded") failures[item.failure_class ?? "unknown"] = (failures[item.failure_class ?? "unknown"] ?? 0) + 1;
  return {
    invocation_count: cases.length,
    success_count: cases.filter((item) => item.status === "succeeded").length,
    failure_counts: failures,
    cost: {
      total: sumFixed8(costs),
      average: averageFixed8(costs),
      complete_accounting_count: costs.length
    },
    latency_ms: {
      sample_count: latencies.length,
      p50: percentileNearestRank(latencies, 0.50),
      p95: percentileNearestRank(latencies, 0.95),
      max: latencies.at(-1) ?? null
    },
    tokens: {
      input: sum(cases, (item) => item.input_tokens ?? 0),
      cached_input: sum(cases, (item) => item.cached_input_tokens ?? 0),
      output: sum(cases, (item) => item.output_tokens ?? 0)
    }
  };
}

export function percentileNearestRank(sortedValues, percentile) {
  if (sortedValues.length === 0) return null;
  return sortedValues[Math.max(0, Math.ceil(percentile * sortedValues.length) - 1)];
}

function aggregateClassification(values) {
  const counts = Object.fromEntries(CLASS_NAMES.map((name) => [name, { tp: 0, fp: 0, fn: 0 }]));
  let correct = 0;
  let aligned = 0;
  for (const value of values) {
    correct += value.correct;
    aligned += value.aligned_decisions;
    for (const name of CLASS_NAMES) for (const key of ["tp", "fp", "fn"]) counts[name][key] += value.per_class[name][key];
  }
  const syntheticGold = [];
  const syntheticPredicted = [];
  for (const name of CLASS_NAMES) {
    const { tp, fp, fn } = counts[name];
    for (let index = 0; index < tp; index += 1) { const id = `${name}:tp:${index}`; syntheticGold.push({ gold_item_id: id, item_type: name }); syntheticPredicted.push({ item_id: id, item_type: name }); }
    for (let index = 0; index < fn; index += 1) syntheticGold.push({ gold_item_id: `${name}:fn:${index}`, item_type: name });
    for (let index = 0; index < fp; index += 1) syntheticPredicted.push({ item_id: `${name}:fp:${index}`, item_type: name });
  }
  const result = calculateClassification(syntheticGold, syntheticPredicted);
  return { ...result, correct, aligned_decisions: aligned };
}

function emptyRequirementEvaluation(fixture, failureClass) {
  const gold = fixture.expected_output.requirements;
  return {
    fixture_id: fixture.fixture_id,
    failure_categories: [`provider_failure:${failureClass ?? "unknown"}`],
    counts: { gold: gold.length, matched_gold: 0, critical_gold: gold.filter((item) => item.critical_for_scope).length, omitted_critical: gold.filter((item) => item.critical_for_scope).length, generated: 0, unsupported: 0, detected_unsupported: 0, duplicate_extras: 0, critical_unsupported_misses: 0 },
    generated_candidate_ids: [], critical_candidate_ids: []
  };
}

function emptyGapEvaluation(fixture, failureClass) {
  const gold = fixture.expected_output.gaps;
  const critical = gold.filter((item) => item.critical_for_scope).length;
  return {
    fixture_id: fixture.fixture_id,
    failure_categories: [`provider_failure:${failureClass ?? "unknown"}`],
    counts: { gold: gold.length, matched_gold: 0, critical_gold: critical, matched_critical: 0, omitted_critical: critical, generated: 0, false_gaps: 0, authoritative_critical: 0, correct_critical: 0, duplicate_extras: 0 },
    generated_candidate_ids: [], critical_candidate_ids: []
  };
}

function totalCounts(values, keys) {
  return Object.fromEntries(keys.map((key) => [key, sum(values, (item) => item.counts[key])]));
}

function safeFixtureResults(values) {
  return values.map((item) => ({ fixture_id: item.fixture_id, failure_categories: item.failure_categories }));
}

function reviewKey(provider, model, suite, fixture) { return `${provider}\u0000${model}\u0000${suite}\u0000${fixture}`; }
function validScore(value) { return Number.isInteger(value) && value >= 1 && value <= 5; }
function validateScoreKeys(value, dimensions, includeReviewer = true) {
  const keys = includeReviewer ? ["reviewer_id", ...dimensions] : dimensions;
  assertExactKeys(value, keys, "scores");
  if (dimensions.some((dimension) => !validScore(value[dimension]))) throw new Error("INVALID_REVIEW_SCORE");
}
function assertExactKeys(value, keys, label) {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).sort().join("\u0000") !== [...keys].sort().join("\u0000")) throw new Error(`INVALID_${label.toUpperCase().replaceAll(" ", "_")}`);
}
function sum(values, selector) { return values.reduce((total, value) => total + selector(value), 0); }
function parseFixed8(value) {
  const match = /^(\d+)(?:\.(\d{1,8}))?$/.exec(String(value));
  if (!match) throw new Error("INVALID_COST_VALUE");
  return BigInt(match[1]) * 100000000n + BigInt((match[2] ?? "").padEnd(8, "0"));
}
function fixed8(value) { const whole = value / 100000000n; const fraction = String(value % 100000000n).padStart(8, "0"); return `${whole}.${fraction}`; }
function sumFixed8(values) { return fixed8(values.reduce((total, value) => total + parseFixed8(value), 0n)); }
function averageFixed8(values) {
  if (values.length === 0) return null;
  const total = values.reduce((result, value) => result + parseFixed8(value), 0n);
  const count = BigInt(values.length);
  return fixed8((total + count / 2n) / count);
}
async function loadThresholds() {
  const load = async (root) => JSON.parse(await readFile(path.join(root, "thresholds.json"), "utf8"));
  return { context: await load(roots.context), requirement: await load(roots.requirement), gap: await load(roots.gap) };
}
