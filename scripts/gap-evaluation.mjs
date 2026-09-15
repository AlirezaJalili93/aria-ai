import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

export const EVAL_SET_ID = "gap_detection_eval_v1";
export const GAP_TYPES = ["missing_information", "ambiguity", "conflict", "unsupported_assumption", "decision_required", "scope_risk"];
export const SEVERITIES = ["critical", "high", "medium", "low"];
export const RULE_IDS = ["CGR-001", "CGR-002", "CGR-003"];
export const FIXTURE_ROOT = path.resolve(process.cwd(), "evals/gap-detection/gap_detection_eval_v1");

const metric = (numerator, denominator) => ({ value: denominator === 0 ? null : numerator / denominator, numerator, denominator });

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

function sourceKey(ref) { return `${ref.source_id}\u0000${ref.source_version_id}`; }

function validSourceRef(ref, sourceLengths = new Map()) {
  if (!ref || typeof ref.source_id !== "string" || typeof ref.source_version_id !== "string") return false;
  const hasStart = ref.start_offset !== undefined && ref.start_offset !== null;
  const hasEnd = ref.end_offset !== undefined && ref.end_offset !== null;
  if (hasStart !== hasEnd) return false;
  if (!hasStart) return true;
  const length = sourceLengths.get(sourceKey(ref));
  return Number.isInteger(ref.start_offset) && Number.isInteger(ref.end_offset) && ref.start_offset >= 0 && ref.end_offset > ref.start_offset && (length === undefined || ref.end_offset <= length);
}

function setEqual(first, second) {
  return first.length === second.length && [...first].sort().every((item, index) => item === [...second].sort()[index]);
}

export function validateFixtureContract(fixture) {
  const failures = [];
  if (!/^fa_gap_\d{3}$/.test(fixture?.fixture_id ?? "")) failures.push("fixture_id");
  if (fixture?.eval_set_id !== EVAL_SET_ID) failures.push("eval_set_id");
  if (fixture?.language !== "fa") failures.push("language");
  if (!["landing", "corporate", "portfolio"].includes(fixture?.project_type)) failures.push("project_type");
  if (!Number.isInteger(fixture?.input?.context_version) || fixture.input.context_version < 1) failures.push("context_version");
  if (!Array.isArray(fixture?.input?.context_items) || !Array.isArray(fixture?.input?.requirements)) failures.push("input");
  if (!Array.isArray(fixture?.expected_output?.gaps) || typeof fixture?.expected_output?.no_gap !== "boolean") failures.push("expected_output");
  if (!Array.isArray(fixture?.evaluation_annotations?.candidate_annotations)) failures.push("candidate_annotations");
  if (!Array.isArray(fixture?.evaluation_annotations?.deterministic_output_candidate_ids)) failures.push("deterministic_output_candidate_ids");
  if (!Array.isArray(fixture?.evaluation_annotations?.semantic_duplicate_groups)) failures.push("semantic_duplicate_groups");
  if (fixture?.metadata?.synthetic !== true || fixture?.metadata?.fixture_version !== "1") failures.push("metadata");

  const sourceLengths = new Map((fixture?.input?.source_versions ?? []).map((source) => [sourceKey(source), source.canonical_length]));
  const availableRefs = new Set(sourceLengths.keys());
  if (!Array.isArray(fixture?.input?.source_versions) || sourceLengths.size !== (fixture?.input?.source_versions ?? []).length) failures.push("source_versions");
  const contextIds = new Set();
  for (const item of fixture?.input?.context_items ?? []) {
    if (!item?.context_item_id || contextIds.has(item.context_item_id)) failures.push("context_item_id");
    contextIds.add(item?.context_item_id);
    if (!(["fact", "assumption", "decision", "constraint", "reference", "unknown"].includes(item?.item_type))) failures.push("context_item_type");
    if (typeof item?.content !== "string" || item.content.length === 0) failures.push("context_item_content");
    if (!Array.isArray(item?.source_refs) || !item.source_refs.every((ref) => validSourceRef(ref, sourceLengths) && sourceLengths.has(sourceKey(ref)))) failures.push("context_item_source_refs");
    for (const ref of item?.source_refs ?? []) availableRefs.add(sourceKey(ref));
  }
  const requirementIds = new Set((fixture?.input?.requirements ?? []).map((item) => item.requirement_id));
  const goldIds = new Set();
  let criticalGoldCount = 0;
  for (const gap of fixture?.expected_output?.gaps ?? []) {
    if (!gap?.gold_gap_id || goldIds.has(gap.gold_gap_id)) failures.push("gold_gap_id");
    goldIds.add(gap.gold_gap_id);
    if (!GAP_TYPES.includes(gap?.gap_type)) failures.push("gold_gap_type");
    if (!SEVERITIES.includes(gap?.severity)) failures.push("gold_severity");
    if (!["empty", "required", "optional"].includes(gap?.source_refs_expectation)) failures.push("gold_source_expectation");
    if (!Array.isArray(gap?.source_refs) || !gap.source_refs.every((ref) => validSourceRef(ref, sourceLengths))) failures.push("gold_source_refs");
    if (!gap.source_refs.every((ref) => availableRefs.has(sourceKey(ref)))) failures.push("unknown_gold_source_ref");
    if (!Array.isArray(gap?.affected_requirement_ids) || !gap.affected_requirement_ids.every((id) => requirementIds.has(id))) failures.push("gold_affected_requirements");
    if (gap.critical_for_scope) {
      criticalGoldCount += 1;
      if (!RULE_IDS.includes(gap.critical_rule_id)) failures.push("critical_gold_rule");
    } else if (gap.critical_rule_id !== null) failures.push("noncritical_gold_rule");
    if (gap.source_refs_expectation === "empty" && gap.source_refs.length !== 0) failures.push("gold_empty_source_refs");
    if (gap.source_refs_expectation === "required" && gap.source_refs.length === 0) failures.push("gold_required_source_refs");
  }
  if (fixture.expected_output.no_gap !== (goldIds.size === 0)) failures.push("no_gap_mismatch");
  const candidateIds = new Set();
  const annotationById = new Map();
  for (const annotation of fixture?.evaluation_annotations?.candidate_annotations ?? []) {
    if (!annotation?.candidate_id || candidateIds.has(annotation.candidate_id)) failures.push("candidate_id");
    candidateIds.add(annotation?.candidate_id);
    annotationById.set(annotation?.candidate_id, annotation);
    if (annotation?.gold_gap_id !== null && !goldIds.has(annotation?.gold_gap_id)) failures.push("unknown_candidate_gold");
    if (typeof annotation?.semantically_unsupported !== "boolean" || typeof annotation?.critical_for_scope !== "boolean") failures.push("candidate_annotation");
    if (!["empty", "required", "optional"].includes(annotation?.source_refs_expectation)) failures.push("candidate_source_expectation");
  }
  const deterministic = new Set();
  for (const candidateId of fixture?.evaluation_annotations?.deterministic_output_candidate_ids ?? []) {
    if (deterministic.has(candidateId)) failures.push("duplicate_deterministic_candidate");
    deterministic.add(candidateId);
    if (!candidateIds.has(candidateId)) failures.push("unknown_deterministic_candidate");
  }
  const grouped = new Set();
  const groups = new Set();
  for (const group of fixture?.evaluation_annotations?.semantic_duplicate_groups ?? []) {
    if (!group?.group_id || groups.has(group.group_id)) failures.push("duplicate_group_id");
    groups.add(group?.group_id);
    if (!Array.isArray(group?.candidate_ids) || group.candidate_ids.length === 0) failures.push("duplicate_group_candidates");
    for (const candidateId of group?.candidate_ids ?? []) {
      if (!candidateIds.has(candidateId) || grouped.has(candidateId)) failures.push("invalid_duplicate_candidate");
      grouped.add(candidateId);
    }
  }
  if (!Array.isArray(fixture?.metadata?.phenomena) || fixture.metadata.phenomena.length === 0) failures.push("phenomena");
  if (failures.length > 0) throw new Error(`Invalid fixture ${fixture?.fixture_id ?? "unknown"}: ${[...new Set(failures)].join(",")}`);
  return { fixture, counts: { gold: goldIds.size, criticalGold: criticalGoldCount }, annotationById };
}

export async function loadFixtures(root = FIXTURE_ROOT) {
  const manifest = JSON.parse(await readFile(path.join(root, "manifest.json"), "utf8"));
  const names = (await readdir(path.join(root, "fixtures"))).filter((name) => name.endsWith(".json")).sort();
  const fixtures = await Promise.all(names.map(async (name) => JSON.parse(await readFile(path.join(root, "fixtures", name), "utf8"))));
  if (fixtures.length !== 20) throw new Error(`Expected 20 J05 fixtures, found ${fixtures.length}`);
  if (manifest.eval_set_id !== EVAL_SET_ID || manifest.expected_fixture_count !== 20 || JSON.stringify(manifest.fixture_ids) !== JSON.stringify(fixtures.map((fixture) => fixture.fixture_id))) throw new Error("J05 manifest does not match fixture inventory");
  const validated = fixtures.map((fixture) => validateFixtureContract(fixture));
  const goldCount = validated.reduce((total, item) => total + item.counts.gold, 0);
  const criticalCount = validated.reduce((total, item) => total + item.counts.criticalGold, 0);
  const types = new Set(fixtures.flatMap((fixture) => fixture.expected_output.gaps.map((gap) => gap.gap_type)));
  const projects = new Set(fixtures.map((fixture) => fixture.project_type));
  if (goldCount === 0 || criticalCount === 0 || !fixtures.some((fixture) => fixture.expected_output.no_gap) || GAP_TYPES.some((type) => !types.has(type)) || projects.size !== 3) throw new Error("INVALID_EVAL_DATASET");
  return fixtures;
}

export class FakeDeterministicProvider {
  constructor() { this.mode = "fake_deterministic"; }

  async execute(fixture) {
    const goldById = new Map(fixture.expected_output.gaps.map((gap) => [gap.gold_gap_id, gap]));
    const annotations = fixture.evaluation_annotations.candidate_annotations;
    return {
      gaps: fixture.evaluation_annotations.deterministic_output_candidate_ids.map((candidateId) => {
        const annotation = annotations.find((item) => item.candidate_id === candidateId);
        const gold = goldById.get(annotation?.gold_gap_id);
        if (!gold) return { candidate_id: candidateId, gap_type: "ambiguity", severity: "medium", source_refs: [], affected_requirement_ids: [], critical_rule_id: null };
        return { candidate_id: candidateId, gap_type: gold.gap_type, severity: gold.severity, source_refs: gold.source_refs, affected_requirement_ids: gold.affected_requirement_ids, critical_rule_id: gold.critical_rule_id };
      })
    };
  }
}

function validateCandidate(candidate, fixture, gold, annotations, failures) {
  if (!candidate || typeof candidate.candidate_id !== "string") failures.push("invalid_candidate_identity");
  if (!GAP_TYPES.includes(candidate?.gap_type)) failures.push("unknown_gap_type");
  if (!SEVERITIES.includes(candidate?.severity)) failures.push("invalid_severity");
  const sourceLengths = new Map(fixture.input.source_versions.map((source) => [sourceKey(source), source.canonical_length]));
  const availableRefs = new Set(sourceLengths.keys());
  if (!Array.isArray(candidate?.source_refs) || !candidate.source_refs.every((ref) => validSourceRef(ref, sourceLengths))) failures.push("invalid_provenance");
  if (!candidate?.source_refs?.every((ref) => validSourceRef(ref, sourceLengths) && availableRefs.has(sourceKey(ref)))) failures.push("invalid_provenance");
  if (!Array.isArray(candidate?.affected_requirement_ids)) failures.push("invalid_affected_requirement_relationship");
  const annotation = annotations.get(candidate?.candidate_id);
  const matchedGold = annotation?.gold_gap_id ? gold.get(annotation.gold_gap_id) : null;
  if (matchedGold) {
    if (candidate.gap_type !== matchedGold.gap_type) failures.push("gap_type_mismatch");
    if (!setEqual(candidate.affected_requirement_ids ?? [], matchedGold.affected_requirement_ids)) failures.push("invalid_affected_requirement_relationship");
    const expectation = matchedGold.source_refs_expectation;
    if (expectation === "empty" && candidate.source_refs.length !== 0) failures.push("invalid_provenance");
    if (expectation === "required" && candidate.source_refs.length === 0) failures.push("invalid_provenance");
    if (candidate.source_refs.some((ref) => !validSourceRef(ref, sourceLengths) || !availableRefs.has(sourceKey(ref)))) failures.push("invalid_provenance");
    if (candidate.severity === "critical" && candidate.critical_rule_id !== matchedGold.critical_rule_id) failures.push("critical_rule_mismatch");
  }
  if (candidate.severity === "critical" && !RULE_IDS.includes(candidate.critical_rule_id)) failures.push("critical_rule_mismatch");
}

export function evaluateOutput(fixture, output) {
  const failures = [];
  const candidates = Array.isArray(output?.gaps) ? output.gaps : [];
  if (!Array.isArray(output?.gaps)) failures.push("invalid_gap_collection");
  const annotations = new Map(fixture.evaluation_annotations.candidate_annotations.map((item) => [item.candidate_id, item]));
  const gold = new Map(fixture.expected_output.gaps.map((item) => [item.gold_gap_id, item]));
  const seenIds = new Set();
  const matchedGold = new Set();
  let authoritativeCritical = 0;
  let correctCritical = 0;
  for (const candidate of candidates) {
    if (seenIds.has(candidate?.candidate_id)) failures.push("duplicate_gap");
    if (typeof candidate?.candidate_id === "string") seenIds.add(candidate.candidate_id);
    const annotation = annotations.get(candidate?.candidate_id);
    if (!annotation) failures.push("unannotated_candidate");
    validateCandidate(candidate, fixture, gold, annotations, failures);
    if (annotation?.gold_gap_id && candidate?.gap_type === gold.get(annotation.gold_gap_id)?.gap_type) matchedGold.add(annotation.gold_gap_id);
    if (candidate?.severity === "critical" && RULE_IDS.includes(candidate?.critical_rule_id)) {
      authoritativeCritical += 1;
      const matched = gold.get(annotation?.gold_gap_id);
      if (matched?.critical_for_scope && matched.critical_rule_id === candidate.critical_rule_id) correctCritical += 1;
    }
  }
  let duplicateExtras = 0;
  for (const group of fixture.evaluation_annotations.semantic_duplicate_groups) {
    const present = group.candidate_ids.filter((id) => seenIds.has(id)).length;
    duplicateExtras += Math.max(0, present - 1);
  }
  if (duplicateExtras > 0) failures.push("duplicate_gap");
  const criticalGold = fixture.expected_output.gaps.filter((gap) => gap.critical_for_scope);
  const omittedCritical = criticalGold.filter((gap) => !matchedGold.has(gap.gold_gap_id)).length;
  const falseGaps = candidates.filter((candidate) => {
    const annotation = annotations.get(candidate?.candidate_id);
    return !annotation?.gold_gap_id || candidate?.gap_type !== gold.get(annotation.gold_gap_id)?.gap_type;
  }).length;
  return {
    fixture_id: fixture.fixture_id,
    failure_categories: [...new Set(failures)],
    counts: {
      gold: fixture.expected_output.gaps.length,
      matched_gold: matchedGold.size,
      critical_gold: criticalGold.length,
      matched_critical: criticalGold.length - omittedCritical,
      omitted_critical: omittedCritical,
      generated: candidates.length,
      false_gaps: falseGaps,
      authoritative_critical: authoritativeCritical,
      correct_critical: correctCritical,
      duplicate_extras: duplicateExtras
    },
    generated_candidate_ids: candidates.map((candidate) => candidate?.candidate_id).filter((id) => typeof id === "string"),
    critical_candidate_ids: candidates.filter((candidate) => candidate?.severity === "critical").map((candidate) => candidate.candidate_id)
  };
}

function validScore(value) { return Number.isInteger(value) && value >= 1 && value <= 5; }

export function calculateHumanReview({ generatedCandidateIds, criticalCandidateIds = [], records = [] }) {
  if (!Array.isArray(generatedCandidateIds) || generatedCandidateIds.length === 0) return { status: "not_applicable", semantic_validity_score: metric(0, 0), critical_semantic_below_3: false };
  if (!Array.isArray(records) || records.length === 0) return { status: "not_run", semantic_validity_score: metric(0, 0), critical_semantic_below_3: false };
  const generated = new Set(generatedCandidateIds);
  const recordById = new Map();
  for (const record of records) {
    if (!generated.has(record?.candidate_id) || recordById.has(record?.candidate_id) || !Array.isArray(record?.reviewers) || record.reviewers.length !== 2) throw new Error("Invalid human review inventory");
    if (record.reviewers[0].reviewer_id === record.reviewers[1].reviewer_id) throw new Error("Reviewers must be independent");
    if (record.reviewers.some((reviewer) => !validScore(reviewer.semantic_validity_score))) throw new Error("Semantic validity scores must be integers from 1 through 5");
    recordById.set(record.candidate_id, record);
  }
  if (recordById.size !== generated.size) return { status: "incomplete", semantic_validity_score: metric(0, 0), critical_semantic_below_3: false };
  const finalScores = [];
  for (const candidateId of generatedCandidateIds) {
    const record = recordById.get(candidateId);
    const [first, second] = record.reviewers.map((reviewer) => reviewer.semantic_validity_score);
    if (Math.abs(first - second) >= 2 && !validScore(record.adjudication?.semantic_validity_score)) return { status: "adjudication_required", semantic_validity_score: metric(0, 0), critical_semantic_below_3: false };
    finalScores.push(record.adjudication?.semantic_validity_score ?? (first + second) / 2);
  }
  const finalById = new Map(generatedCandidateIds.map((candidateId, index) => [candidateId, finalScores[index]]));
  const critical = new Set(criticalCandidateIds);
  return { status: "scored", semantic_validity_score: metric(finalScores.reduce((sum, value) => sum + value, 0), finalScores.length), critical_semantic_below_3: [...critical].some((candidateId) => (finalById.get(candidateId) ?? 5) < 3) };
}

export async function runEvaluation({ root = FIXTURE_ROOT, provider = new FakeDeterministicProvider(), humanReviewRecords = [] } = {}) {
  if (provider.mode !== "fake_deterministic") throw new Error("Real Provider evaluation remains deferred to G02/G03");
  const fixtures = await loadFixtures(root);
  const thresholds = JSON.parse(await readFile(path.join(root, "thresholds.json"), "utf8"));
  const evaluated = [];
  for (const fixture of fixtures) evaluated.push(evaluateOutput(fixture, await provider.execute(fixture)));
  const totals = evaluated.reduce((sum, item) => {
    for (const key of Object.keys(sum)) sum[key] += item.counts[key];
    return sum;
  }, { gold: 0, matched_gold: 0, critical_gold: 0, matched_critical: 0, omitted_critical: 0, generated: 0, false_gaps: 0, authoritative_critical: 0, correct_critical: 0, duplicate_extras: 0 });
  const human = calculateHumanReview({ generatedCandidateIds: evaluated.flatMap((item) => item.generated_candidate_ids), criticalCandidateIds: evaluated.flatMap((item) => item.critical_candidate_ids), records: humanReviewRecords });
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
    eval_set_id: EVAL_SET_ID,
    report_version: "1",
    provider_mode: provider.mode,
    fixture_count: fixtures.length,
    metrics,
    threshold_assessments: Object.fromEntries(Object.entries(metrics).map(([name, value]) => [name, assessThreshold(value.value, thresholds.metrics[name])])),
    critical_blockers: blockers,
    human_review_status: human.status,
    contract_gate: { status: evaluated.every((item) => item.failure_categories.length === 0) ? "pass" : "fail" },
    model_quality_gate: { status: "not_run", reason: "real_provider_and_human_review_required" },
    fixtures: evaluated.map((item) => ({ fixture_id: item.fixture_id, gold_count: item.counts.gold, generated_count: item.counts.generated, failure_categories: item.failure_categories }))
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))) {
  const outputIndex = process.argv.indexOf("--output");
  const report = await runEvaluation();
  const serialized = `${JSON.stringify(report, null, 2)}\n`;
  if (outputIndex >= 0) { const outputPath = path.resolve(process.argv[outputIndex + 1]); await mkdir(path.dirname(outputPath), { recursive: true }); await writeFile(outputPath, serialized, "utf8"); }
  else process.stdout.write(serialized);
}
