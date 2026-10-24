import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

export const EVAL_SET_ID = "requirement_extraction_eval_v1";
export const CATEGORIES = ["functional", "content", "visual", "technical", "constraint", "business"];
export const PRIORITIES = ["must", "should", "could"];
const FIXTURE_ROOT = path.resolve(process.cwd(), "evals/requirement-extraction/requirement_extraction_eval_v1");

function metric(numerator, denominator) {
  return { value: denominator === 0 ? null : numerator / denominator, numerator, denominator };
}

export function assessThreshold(value, contract) {
  if (value === null || value === undefined) return "not_run";
  if (contract.direction === "higher") {
    if (value >= contract.target) return "target";
    if (value >= contract.minimum_acceptable) return "minimum_acceptable";
    if (value < contract.release_blocker_below) return "release_blocker";
    return "below_minimum";
  }
  if (contract.direction === "lower") {
    if (value <= contract.target) return "target";
    if (value <= contract.minimum_acceptable) return "minimum_acceptable";
    if (value > contract.release_blocker_above) return "release_blocker";
    return "above_minimum";
  }
  throw new Error("Unknown threshold direction");
}

function assertKeys(value, allowed, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`Invalid ${label}`);
  const extras = Object.keys(value).filter((key) => !allowed.includes(key));
  if (extras.length > 0) throw new Error(`Invalid ${label} fields: ${extras.join(",")}`);
}

function validSourceRef(ref) {
  if (!ref || typeof ref.source_id !== "string" || typeof ref.source_version_id !== "string") return false;
  const hasStart = ref.start_offset !== undefined && ref.start_offset !== null;
  const hasEnd = ref.end_offset !== undefined && ref.end_offset !== null;
  if (hasStart !== hasEnd) return false;
  if (!hasStart) return true;
  return Number.isInteger(ref.start_offset) && Number.isInteger(ref.end_offset) && ref.start_offset >= 0 && ref.end_offset > ref.start_offset;
}

function sourceKey(ref) {
  return `${ref.source_id}\u0000${ref.source_version_id}`;
}

export function validateFixtureContract(fixture) {
  const failures = [];
  if (!/^fa_req_\d{3}$/.test(fixture?.fixture_id ?? "")) failures.push("fixture_id");
  if (fixture?.eval_set_id !== EVAL_SET_ID) failures.push("eval_set_id");
  if (fixture?.language !== "fa") failures.push("language");
  if (!["landing", "corporate", "portfolio"].includes(fixture?.project_type)) failures.push("project_type");
  if (!Number.isInteger(fixture?.input?.context_version) || fixture.input.context_version < 1) failures.push("context_version");
  if (!Array.isArray(fixture?.input?.context_items)) failures.push("context_items");
  if (!Array.isArray(fixture?.expected_output?.requirements)) failures.push("gold_requirements");
  if (!Array.isArray(fixture?.evaluation_annotations?.candidate_annotations)) failures.push("candidate_annotations");
  if (!Array.isArray(fixture?.evaluation_annotations?.deterministic_output_candidate_ids)) failures.push("deterministic_output_candidate_ids");
  if (!Array.isArray(fixture?.evaluation_annotations?.semantic_duplicate_groups)) failures.push("semantic_duplicate_groups");
  if (fixture?.metadata?.synthetic !== true || fixture?.metadata?.fixture_version !== "1") failures.push("metadata");

  const availableRefs = new Set();
  const contextIds = new Set();
  for (const item of fixture?.input?.context_items ?? []) {
    if (!item?.context_item_id || contextIds.has(item.context_item_id)) failures.push("context_item_id");
    contextIds.add(item?.context_item_id);
    if (!["fact", "assumption", "decision", "constraint", "reference", "unknown"].includes(item?.item_type)) failures.push("context_item_type");
    if (typeof item?.content !== "string" || item.content.length === 0) failures.push("context_item_content");
    if (!["proposed", "confirmed"].includes(item?.status)) failures.push("context_item_status");
    if (!Array.isArray(item?.source_refs) || !item.source_refs.every(validSourceRef)) failures.push("context_item_source_refs");
    for (const ref of item?.source_refs ?? []) availableRefs.add(sourceKey(ref));
  }

  const goldIds = new Set();
  for (const requirement of fixture?.expected_output?.requirements ?? []) {
    if (!requirement?.gold_requirement_id || goldIds.has(requirement.gold_requirement_id)) failures.push("gold_requirement_id");
    goldIds.add(requirement?.gold_requirement_id);
    if (typeof requirement?.title !== "string" || typeof requirement?.description !== "string") failures.push("gold_text");
    if (!CATEGORIES.includes(requirement?.category)) failures.push("gold_category");
    if (!PRIORITIES.includes(requirement?.priority)) failures.push("gold_priority");
    if (typeof requirement?.is_unsupported !== "boolean" || typeof requirement?.critical_for_scope !== "boolean") failures.push("gold_annotations");
    if (!Array.isArray(requirement?.source_refs) || !requirement.source_refs.every(validSourceRef)) failures.push("gold_source_refs");
    if (requirement?.is_unsupported === false && requirement?.source_refs?.length === 0) failures.push("supported_without_source");
    for (const ref of requirement?.source_refs ?? []) if (!availableRefs.has(sourceKey(ref))) failures.push("unknown_gold_source_ref");
  }

  const candidateIds = new Set();
  const annotationById = new Map();
  for (const annotation of fixture?.evaluation_annotations?.candidate_annotations ?? []) {
    if (!annotation?.candidate_id || candidateIds.has(annotation.candidate_id)) failures.push("candidate_id");
    candidateIds.add(annotation?.candidate_id);
    annotationById.set(annotation?.candidate_id, annotation);
    if (annotation?.gold_requirement_id !== null && !goldIds.has(annotation?.gold_requirement_id)) failures.push("unknown_candidate_gold");
    if (typeof annotation?.semantically_unsupported !== "boolean" || typeof annotation?.critical_for_scope !== "boolean") failures.push("candidate_semantics");
  }
  const deterministicCandidateIds = new Set();
  for (const candidateId of fixture?.evaluation_annotations?.deterministic_output_candidate_ids ?? []) {
    if (deterministicCandidateIds.has(candidateId)) failures.push("duplicate_deterministic_candidate");
    deterministicCandidateIds.add(candidateId);
    if (!candidateIds.has(candidateId)) failures.push("unknown_deterministic_candidate");
    const annotation = annotationById.get(candidateId);
    if (annotation?.gold_requirement_id === null) failures.push("deterministic_candidate_without_gold");
  }

  const groupedCandidates = new Set();
  const groupIds = new Set();
  for (const group of fixture?.evaluation_annotations?.semantic_duplicate_groups ?? []) {
    if (!group?.group_id || groupIds.has(group.group_id)) failures.push("duplicate_group_id");
    groupIds.add(group?.group_id);
    if (!Array.isArray(group?.candidate_ids) || group.candidate_ids.length === 0) failures.push("duplicate_group_candidates");
    for (const candidateId of group?.candidate_ids ?? []) {
      if (!candidateIds.has(candidateId) || groupedCandidates.has(candidateId)) failures.push("invalid_duplicate_candidate");
      groupedCandidates.add(candidateId);
    }
  }
  if (!Array.isArray(fixture?.metadata?.phenomena) || fixture.metadata.phenomena.length === 0) failures.push("phenomena");
  if (failures.length > 0) throw new Error(`Invalid fixture ${fixture?.fixture_id ?? "unknown"}: ${[...new Set(failures)].join(",")}`);
  return fixture;
}

export async function loadFixtures(root = FIXTURE_ROOT) {
  const manifest = JSON.parse(await readFile(path.join(root, "manifest.json"), "utf8"));
  const fixtureDirectory = path.join(root, "fixtures");
  const names = (await readdir(fixtureDirectory)).filter((name) => name.endsWith(".json")).sort();
  const fixtures = await Promise.all(names.map(async (name) => validateFixtureContract(JSON.parse(await readFile(path.join(fixtureDirectory, name), "utf8")))));
  if (fixtures.length !== 20) throw new Error(`Expected 20 I05 fixtures, found ${fixtures.length}`);
  if (manifest.eval_set_id !== EVAL_SET_ID || manifest.expected_fixture_count !== fixtures.length || JSON.stringify(manifest.fixture_ids) !== JSON.stringify(fixtures.map((fixture) => fixture.fixture_id))) {
    throw new Error("I05 manifest does not match fixture inventory");
  }
  const goldCount = fixtures.reduce((total, fixture) => total + fixture.expected_output.requirements.length, 0);
  const criticalCount = fixtures.reduce((total, fixture) => total + fixture.expected_output.requirements.filter((item) => item.critical_for_scope).length, 0);
  if (goldCount === 0 || criticalCount === 0) throw new Error("I05 dataset requires non-zero Gold and critical-Gold denominators");
  return fixtures;
}

export class FakeDeterministicProvider {
  constructor() {
    this.mode = "fake_deterministic";
  }

  async execute(fixture) {
    const goldById = new Map(fixture.expected_output.requirements.map((item) => [item.gold_requirement_id, item]));
    const annotationById = new Map(fixture.evaluation_annotations.candidate_annotations.map((item) => [item.candidate_id, item]));
    return {
      requirements: fixture.evaluation_annotations.deterministic_output_candidate_ids.map((candidateId) => {
        const annotation = annotationById.get(candidateId);
        const gold = goldById.get(annotation.gold_requirement_id);
        return {
          candidate_id: candidateId,
          title: gold.title,
          description: gold.description,
          category: gold.category,
          priority: gold.priority,
          source_refs: gold.source_refs,
          is_unsupported: gold.is_unsupported
        };
      })
    };
  }
}

function validateCandidate(candidate, availableRefs, categories) {
  if (!candidate || typeof candidate.candidate_id !== "string") categories.push("invalid_candidate_identity");
  if (typeof candidate?.title !== "string" || typeof candidate?.description !== "string") categories.push("invalid_candidate_text");
  if (!CATEGORIES.includes(candidate?.category)) categories.push("invalid_candidate_category");
  if (!PRIORITIES.includes(candidate?.priority)) categories.push("invalid_candidate_priority");
  if (typeof candidate?.is_unsupported !== "boolean") categories.push("invalid_support_flag");
  if (!Array.isArray(candidate?.source_refs) || !candidate.source_refs.every(validSourceRef)) categories.push("invalid_candidate_source_refs");
  for (const ref of candidate?.source_refs ?? []) if (!availableRefs.has(sourceKey(ref))) categories.push("unavailable_candidate_source_ref");
  if (candidate?.is_unsupported === false && candidate?.source_refs?.length === 0) categories.push("missing_supported_provenance");
}

export function evaluateOutput(fixture, output) {
  const failureCategories = [];
  const candidates = Array.isArray(output?.requirements) ? output.requirements : [];
  if (!Array.isArray(output?.requirements)) failureCategories.push("invalid_requirement_collection");
  const annotations = new Map(fixture.evaluation_annotations.candidate_annotations.map((item) => [item.candidate_id, item]));
  const gold = fixture.expected_output.requirements;
  const goldById = new Map(gold.map((item) => [item.gold_requirement_id, item]));
  const availableRefs = new Set(fixture.input.context_items.flatMap((item) => item.source_refs).map(sourceKey));
  const seenCandidateIds = new Set();
  const presentCandidateIds = new Set();
  const matchedGoldIds = new Set();
  let unsupported = 0;
  let detectedUnsupported = 0;
  let criticalUnsupportedMisses = 0;

  for (const candidate of candidates) {
    validateCandidate(candidate, availableRefs, failureCategories);
    if (seenCandidateIds.has(candidate?.candidate_id)) failureCategories.push("duplicate_candidate_identity");
    if (typeof candidate?.candidate_id === "string") {
      seenCandidateIds.add(candidate.candidate_id);
      presentCandidateIds.add(candidate.candidate_id);
    }
    const annotation = annotations.get(candidate?.candidate_id);
    if (!annotation) {
      failureCategories.push("unannotated_candidate");
      continue;
    }
    if (annotation.gold_requirement_id !== null) matchedGoldIds.add(annotation.gold_requirement_id);
    if (annotation.semantically_unsupported) {
      unsupported += 1;
      if (candidate?.is_unsupported === true) detectedUnsupported += 1;
      else if (annotation.critical_for_scope) criticalUnsupportedMisses += 1;
    }
  }

  const criticalGoldIds = new Set(gold.filter((item) => item.critical_for_scope).map((item) => item.gold_requirement_id));
  const omittedCritical = [...criticalGoldIds].filter((id) => !matchedGoldIds.has(id)).length;
  let duplicateExtras = 0;
  for (const group of fixture.evaluation_annotations.semantic_duplicate_groups) {
    const present = group.candidate_ids.filter((id) => presentCandidateIds.has(id)).length;
    duplicateExtras += Math.max(0, present - 1);
  }
  for (const matchedId of matchedGoldIds) if (!goldById.has(matchedId)) failureCategories.push("unknown_matched_gold");

  return {
    fixture_id: fixture.fixture_id,
    failure_categories: [...new Set(failureCategories)],
    counts: {
      gold: gold.length,
      matched_gold: matchedGoldIds.size,
      critical_gold: criticalGoldIds.size,
      omitted_critical: omittedCritical,
      generated: candidates.length,
      unsupported,
      detected_unsupported: detectedUnsupported,
      duplicate_extras: duplicateExtras,
      critical_unsupported_misses: criticalUnsupportedMisses
    },
    generated_candidate_ids: [...presentCandidateIds],
    critical_candidate_ids: candidates
      .filter((candidate) => {
        const annotation = annotations.get(candidate?.candidate_id);
        return annotation?.critical_for_scope === true || (annotation?.gold_requirement_id !== null && goldById.get(annotation?.gold_requirement_id)?.critical_for_scope === true);
      })
      .map((candidate) => candidate.candidate_id)
  };
}

function validScore(value) {
  return Number.isInteger(value) && value >= 1 && value <= 5;
}

function resolveDimension(first, second, adjudicated) {
  if (!validScore(first) || !validScore(second)) throw new Error("Reviewer scores must be integers from 1 through 5");
  if (Math.abs(first - second) >= 2) {
    if (!validScore(adjudicated)) return { status: "adjudication_required", value: null };
    return { status: "adjudicated", value: adjudicated };
  }
  return { status: "agreed", value: (first + second) / 2 };
}

export function calculateHumanReview({ generatedCandidateIds, criticalCandidateIds = [], records = [] }) {
  if (!Array.isArray(generatedCandidateIds) || generatedCandidateIds.length === 0) {
    return {
      status: "not_applicable",
      clarity_score: metric(0, 0),
      actionability_score: metric(0, 0),
      critical_clarity_below_3: false,
      critical_actionability_below_3: false
    };
  }
  if (!Array.isArray(records) || records.length === 0) {
    return {
      status: "not_run",
      clarity_score: metric(0, 0),
      actionability_score: metric(0, 0),
      critical_clarity_below_3: false,
      critical_actionability_below_3: false
    };
  }
  const generated = new Set(generatedCandidateIds);
  const critical = new Set(criticalCandidateIds);
  const recordById = new Map();
  for (const record of records) {
    assertKeys(record, ["candidate_id", "reviewers", "adjudication"], "human review record");
    if (!generated.has(record.candidate_id) || recordById.has(record.candidate_id)) throw new Error("Human review candidate inventory mismatch");
    if (!Array.isArray(record.reviewers) || record.reviewers.length !== 2) throw new Error("Exactly two reviewers are required");
    for (const reviewer of record.reviewers) assertKeys(reviewer, ["reviewer_id", "clarity_score", "actionability_score"], "reviewer score");
    if (record.reviewers[0].reviewer_id === record.reviewers[1].reviewer_id) throw new Error("Reviewers must be independent");
    if (record.adjudication !== undefined) assertKeys(record.adjudication, ["clarity_score", "actionability_score"], "adjudication");
    recordById.set(record.candidate_id, record);
  }
  if (recordById.size !== generated.size) {
    return {
      status: "incomplete",
      clarity_score: metric(0, 0),
      actionability_score: metric(0, 0),
      critical_clarity_below_3: false,
      critical_actionability_below_3: false
    };
  }

  const finalScores = [];
  let needsAdjudication = false;
  for (const candidateId of generatedCandidateIds) {
    const record = recordById.get(candidateId);
    const clarity = resolveDimension(record.reviewers[0].clarity_score, record.reviewers[1].clarity_score, record.adjudication?.clarity_score);
    const actionability = resolveDimension(record.reviewers[0].actionability_score, record.reviewers[1].actionability_score, record.adjudication?.actionability_score);
    if (clarity.value === null || actionability.value === null) needsAdjudication = true;
    finalScores.push({ candidate_id: candidateId, clarity: clarity.value, actionability: actionability.value });
  }
  if (needsAdjudication) {
    return {
      status: "adjudication_required",
      clarity_score: metric(0, 0),
      actionability_score: metric(0, 0),
      critical_clarity_below_3: false,
      critical_actionability_below_3: false
    };
  }
  const clarityTotal = finalScores.reduce((total, item) => total + item.clarity, 0);
  const actionabilityTotal = finalScores.reduce((total, item) => total + item.actionability, 0);
  return {
    status: "scored",
    clarity_score: metric(clarityTotal, finalScores.length),
    actionability_score: metric(actionabilityTotal, finalScores.length),
    critical_clarity_below_3: finalScores.some((item) => critical.has(item.candidate_id) && item.clarity < 3),
    critical_actionability_below_3: finalScores.some((item) => critical.has(item.candidate_id) && item.actionability < 3)
  };
}

export async function runEvaluation({ root = FIXTURE_ROOT, provider = new FakeDeterministicProvider(), humanReviewRecords = [] } = {}) {
  if (provider.mode !== "fake_deterministic") throw new Error("Real Provider evaluation remains deferred to G02/G03");
  const fixtures = await loadFixtures(root);
  const thresholds = JSON.parse(await readFile(path.join(root, "thresholds.json"), "utf8"));
  const evaluated = [];
  for (const fixture of fixtures) evaluated.push(evaluateOutput(fixture, await provider.execute(fixture)));
  const totals = evaluated.reduce((result, item) => {
    for (const key of Object.keys(result)) result[key] += item.counts[key];
    return result;
  }, {
    gold: 0,
    matched_gold: 0,
    critical_gold: 0,
    omitted_critical: 0,
    generated: 0,
    unsupported: 0,
    detected_unsupported: 0,
    duplicate_extras: 0,
    critical_unsupported_misses: 0
  });
  const generatedCandidateIds = evaluated.flatMap((item) => item.generated_candidate_ids);
  const criticalCandidateIds = evaluated.flatMap((item) => item.critical_candidate_ids);
  const human = calculateHumanReview({ generatedCandidateIds, criticalCandidateIds, records: humanReviewRecords });
  const metrics = {
    requirement_recall: metric(totals.matched_gold, totals.gold),
    critical_omission_rate: metric(totals.omitted_critical, totals.critical_gold),
    unsupported_output_rate: metric(totals.unsupported, totals.generated),
    unsupported_detection_rate: metric(totals.detected_unsupported, totals.unsupported),
    duplicate_rate: metric(totals.duplicate_extras, totals.generated),
    clarity_score: human.clarity_score,
    actionability_score: human.actionability_score
  };
  const criticalBlockers = [];
  if (totals.omitted_critical > 0) criticalBlockers.push("critical_gold_unmatched");
  if (totals.critical_unsupported_misses > 0) criticalBlockers.push("critical_unsupported_not_detected");
  if (human.critical_clarity_below_3) criticalBlockers.push("critical_clarity_below_3");
  if (human.critical_actionability_below_3) criticalBlockers.push("critical_actionability_below_3");
  return {
    eval_set_id: EVAL_SET_ID,
    report_version: "1",
    provider_mode: provider.mode,
    fixture_count: fixtures.length,
    metrics,
    threshold_assessments: Object.fromEntries(Object.entries(metrics).map(([name, value]) => [name, assessThreshold(value.value, thresholds.metrics[name])])),
    critical_blockers: criticalBlockers,
    human_review_status: human.status,
    contract_gate: { status: evaluated.every((item) => item.failure_categories.length === 0) ? "pass" : "fail" },
    model_quality_gate: { status: "not_run", reason: "real_provider_and_human_review_required" },
    fixtures: evaluated.map((item) => ({
      fixture_id: item.fixture_id,
      gold_count: item.counts.gold,
      generated_count: item.counts.generated,
      failure_categories: item.failure_categories
    }))
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))) {
  const outputIndex = process.argv.indexOf("--output");
  const outputPath = outputIndex >= 0 ? process.argv[outputIndex + 1] : null;
  const report = await runEvaluation();
  const serialized = `${JSON.stringify(report, null, 2)}\n`;
  if (outputPath) {
    const resolvedOutput = path.resolve(outputPath);
    await mkdir(path.dirname(resolvedOutput), { recursive: true });
    await writeFile(resolvedOutput, serialized, "utf8");
  } else process.stdout.write(serialized);
}
