import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

export const CLASS_NAMES = ["fact", "assumption", "decision", "constraint", "reference", "unknown"];
export const EVAL_SET_ID = "context_structuring_eval_v1";
const FIXTURE_ROOT = path.resolve(process.cwd(), "evals/context-structuring/context_structuring_eval_v1");

function metric(value, numerator, denominator) {
  return { value: denominator === 0 ? null : value, numerator, denominator };
}

export function calculatePersianQuality(scores) {
  if (!Array.isArray(scores) || scores.length === 0) {
    return { value: null, numerator: 0, denominator: 0, status: "not_run" };
  }
  const numerator = scores.reduce((sum, score) => sum + score, 0);
  return { value: numerator / (5 * scores.length), numerator, denominator: scores.length, status: "scored" };
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

export function calculateClassification(goldItems, predictedItems) {
  const goldById = new Map(goldItems.map((item) => [item.gold_item_id, item]));
  const classifiableItems = predictedItems.filter((item) => item && typeof item.item_id === "string" && CLASS_NAMES.includes(item.item_type));
  const predictedById = new Map(classifiableItems.map((item) => [item.item_id, item]));
  const counts = Object.fromEntries(CLASS_NAMES.map((name) => [name, { tp: 0, fp: 0, fn: 0 }]));
  let correct = 0;
  for (const gold of goldItems) {
    const predicted = predictedById.get(gold.gold_item_id);
    if (!predicted) {
      counts[gold.item_type].fn += 1;
    } else if (predicted.item_type === gold.item_type) {
      counts[gold.item_type].tp += 1;
      correct += 1;
    } else {
      counts[gold.item_type].fn += 1;
      counts[predicted.item_type].fp += 1;
    }
  }
  for (const predicted of classifiableItems) {
    if (!goldById.has(predicted.item_id)) counts[predicted.item_type].fp += 1;
  }
  const perClass = Object.fromEntries(CLASS_NAMES.map((name) => {
    const { tp, fp, fn } = counts[name];
    const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
    const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
    const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall);
    return [name, { tp, fp, fn, precision, recall, f1 }];
  }));
  const alignedDecisions = goldItems.length + classifiableItems.filter((item) => !goldById.has(item.item_id)).length + (predictedItems.length - classifiableItems.length);
  return {
    accuracy: alignedDecisions === 0 ? null : correct / alignedDecisions,
    macro_f1: perClass === null ? null : CLASS_NAMES.reduce((sum, name) => sum + perClass[name].f1, 0) / CLASS_NAMES.length,
    aligned_decisions: alignedDecisions,
    correct,
    per_class: perClass
  };
}

export function validateFixtureContract(fixture) {
  const failures = [];
  const labelKeys = ["clarity", "has_assumption", "has_constraint", "has_decision", "requires_unknown", "prompt_injection", "unsupported_assumption"];
  if (!/^fa_ctx_\d{3}$/.test(fixture?.fixture_id ?? "")) failures.push("fixture_id");
  if (fixture?.eval_set_id !== EVAL_SET_ID) failures.push("eval_set_id");
  if (fixture?.language !== "fa") failures.push("language");
  if (!["landing", "corporate", "portfolio"].includes(fixture?.project_type)) failures.push("project_type");
  if (!Array.isArray(fixture?.input?.sources) || fixture.input.sources.length === 0) failures.push("sources");
  if (!Array.isArray(fixture?.expected_structured_output?.items)) failures.push("gold_items");
  if (!Array.isArray(fixture?.expected_structured_output?.forbidden_claims)) failures.push("forbidden_claims");
  if (!Array.isArray(fixture?.expected_structured_output?.required_item_ids)) failures.push("required_item_ids");
  if (labelKeys.some((key) => !(key in (fixture?.expected_labels ?? {})))) failures.push("expected_labels");
  if (!Array.isArray(fixture?.provenance_expectations?.allowed_source_ids) || !Array.isArray(fixture?.provenance_expectations?.trace_required_item_ids)) failures.push("provenance_expectations");
  if (fixture?.metadata?.synthetic !== true || fixture?.metadata?.fixture_version !== "1") failures.push("metadata");
  const sourceIds = new Set();
  for (const source of fixture?.input?.sources ?? []) {
    if (!source?.source_id || !source?.source_version_id || typeof source?.canonical_text !== "string" || source.canonical_text.length === 0) failures.push("source_shape");
    if (sourceIds.has(source?.source_id)) failures.push("duplicate_source_id");
    sourceIds.add(source?.source_id);
  }
  const goldIds = new Set();
  for (const item of fixture?.expected_structured_output?.items ?? []) {
    if (!item?.gold_item_id || goldIds.has(item.gold_item_id)) failures.push("gold_item_id");
    goldIds.add(item?.gold_item_id);
    if (!CLASS_NAMES.includes(item?.item_type)) failures.push("gold_item_type");
    if (typeof item?.content !== "string" || item.content.trim() === "") failures.push("gold_content");
    if (typeof item?.trace_required !== "boolean" || !validSourceRefs(fixture, item?.source_refs)) failures.push("gold_provenance");
    if (item?.trace_required === true && item.source_refs.length === 0) failures.push("gold_required_trace");
  }
  for (const itemId of fixture?.expected_structured_output?.required_item_ids ?? []) {
    if (!goldIds.has(itemId)) failures.push("unknown_required_item_id");
  }
  for (const sourceId of fixture?.provenance_expectations?.allowed_source_ids ?? []) {
    if (!sourceIds.has(sourceId)) failures.push("unknown_allowed_source_id");
  }
  for (const itemId of fixture?.provenance_expectations?.trace_required_item_ids ?? []) {
    if (!goldIds.has(itemId)) failures.push("unknown_trace_required_item_id");
  }
  const outcome = fixture?.failure_expectations?.expected_outcome;
  if (!["success", "repair_then_success", "fail"].includes(outcome)) failures.push("expected_outcome");
  if (!Array.isArray(fixture?.failure_expectations?.allowed_failure_codes)) failures.push("allowed_failure_codes");
  if (outcome === "fail" && fixture.failure_expectations.allowed_failure_codes.length === 0) failures.push("missing_failure_code");
  if (failures.length > 0) throw new Error(`Invalid fixture ${fixture?.fixture_id ?? "unknown"}: ${[...new Set(failures)].join(",")}`);
  return fixture;
}

export async function loadFixtures(root = FIXTURE_ROOT) {
  const fixtureDirectory = path.join(root, "fixtures");
  const manifest = JSON.parse(await readFile(path.join(root, "manifest.json"), "utf8"));
  const names = (await readdir(fixtureDirectory)).filter((name) => name.endsWith(".json")).sort();
  const fixtures = await Promise.all(names.map(async (name) => validateFixtureContract(JSON.parse(await readFile(path.join(fixtureDirectory, name), "utf8")))));
  if (fixtures.length !== 20) throw new Error(`Expected 20 H05 fixtures, found ${fixtures.length}`);
  if (manifest.expected_fixture_count !== fixtures.length || JSON.stringify(manifest.fixture_ids) !== JSON.stringify(fixtures.map((fixture) => fixture.fixture_id))) {
    throw new Error("H05 manifest does not match fixture inventory");
  }
  return fixtures;
}

export class FakeDeterministicProvider {
  constructor() {
    this.mode = "fake_deterministic";
  }

  async execute(fixture) {
    const expected = fixture.expected_structured_output;
    if (fixture.failure_expectations.expected_outcome === "fail") {
      return {
        items: [],
        failure: { code: fixture.failure_expectations.allowed_failure_codes[0] },
        repair_attempted: false
      };
    }
    return {
      items: expected.items.map((item) => ({
        item_id: item.gold_item_id,
        item_type: item.item_type,
        content: item.content,
        source_refs: item.source_refs
      })),
      failure: null,
      repair_attempted: false
    };
  }
}

function sourceIndex(fixture) {
  return new Map(fixture.input.sources.map((source) => [source.source_id, source.source_version_id]));
}

function validSourceRefs(fixture, refs) {
  if (!Array.isArray(refs)) return false;
  const sources = sourceIndex(fixture);
  return refs.every((ref) => {
    if (!ref || typeof ref.source_id !== "string" || typeof ref.source_version_id !== "string") return false;
    if (sources.get(ref.source_id) !== ref.source_version_id) return false;
    if (ref.start_offset === undefined && ref.end_offset === undefined) return true;
    if (!Number.isInteger(ref.start_offset) || !Number.isInteger(ref.end_offset)) return false;
    const text = fixture.input.sources.find((source) => source.source_id === ref.source_id)?.canonical_text ?? "";
    return ref.start_offset >= 0 && ref.start_offset < ref.end_offset && ref.end_offset <= text.length;
  });
}

function containsForbiddenClaim(content, forbiddenClaims) {
  const normalized = String(content).toLocaleLowerCase("fa");
  return forbiddenClaims.some((claim) => normalized.includes(String(claim).toLocaleLowerCase("fa")));
}

export function evaluateOutput(fixture, output) {
  const categories = [];
  const items = Array.isArray(output?.items) ? output.items : [];
  const goldItems = fixture.expected_structured_output.items;
  const goldById = new Map(goldItems.map((item) => [item.gold_item_id, item]));
  const uniqueIds = new Set();
  for (const item of items) {
    if (!item || typeof item.item_id !== "string" || uniqueIds.has(item.item_id)) categories.push("invalid_item_identity");
    uniqueIds.add(item?.item_id);
    if (!CLASS_NAMES.includes(item?.item_type)) categories.push("invalid_item_type");
    if (typeof item?.content !== "string" || item.content.trim() === "") categories.push("empty_item_content");
    if (!validSourceRefs(fixture, item?.source_refs)) categories.push("invalid_provenance");
    if (goldById.get(item?.item_id)?.trace_required === true && (!Array.isArray(item?.source_refs) || item.source_refs.length === 0)) categories.push("missing_required_trace");
  }
  const expectedFailure = fixture.failure_expectations.expected_outcome === "fail";
  if (expectedFailure) {
    if (items.length !== 0) categories.push("persisted_items_on_failure");
    if (!fixture.failure_expectations.allowed_failure_codes.includes(output?.failure?.code)) categories.push("unexpected_failure_code");
  } else if (output?.failure) {
    categories.push("unexpected_failure");
  }
  const eligible = items.filter((item) => item && (goldById.get(item.item_id)?.trace_required === true || item.item_type === "fact"));
  const validTraced = eligible.filter((item) => Array.isArray(item.source_refs) && item.source_refs.length > 0 && validSourceRefs(fixture, item.source_refs)).length;
  const predictedAssumptions = items.filter((item) => item?.item_type === "assumption");
  const unsupportedAssumptions = predictedAssumptions.filter((item) => !Array.isArray(item.source_refs) || item.source_refs.length === 0 || containsForbiddenClaim(item.content, fixture.expected_structured_output.forbidden_claims));
  const classification = calculateClassification(goldItems, items);
  return {
    fixture_id: fixture.fixture_id,
    outcome: expectedFailure ? "fail" : "success",
    failure_categories: [...new Set(categories)],
    source_trace: { valid: validTraced, eligible: eligible.length },
    unsupported_assumptions: { unsupported: unsupportedAssumptions.length, predicted: predictedAssumptions.length },
    classification,
    first_pass_valid: categories.length === 0 && output?.repair_attempted !== true,
    json_valid: output !== null && typeof output === "object"
  };
}

export async function runEvaluation({ root = FIXTURE_ROOT, provider = new FakeDeterministicProvider(), persianScores = [] } = {}) {
  const fixtures = await loadFixtures(root);
  const thresholds = JSON.parse(await readFile(path.join(root, "thresholds.json"), "utf8"));
  const evaluated = [];
  for (const fixture of fixtures) evaluated.push(evaluateOutput(fixture, await provider.execute(fixture)));
  const eligible = evaluated.reduce((total, item) => total + item.source_trace.eligible, 0);
  const traced = evaluated.reduce((total, item) => total + item.source_trace.valid, 0);
  const assumptions = evaluated.reduce((total, item) => total + item.unsupported_assumptions.predicted, 0);
  const unsupported = evaluated.reduce((total, item) => total + item.unsupported_assumptions.unsupported, 0);
  const classification = evaluated.reduce((aggregate, item) => {
    aggregate.correct += item.classification.correct;
    aggregate.aligned += item.classification.aligned_decisions;
    for (const name of CLASS_NAMES) {
      for (const key of ["tp", "fp", "fn"]) aggregate.perClass[name][key] += item.classification.per_class[name][key];
    }
    return aggregate;
  }, { correct: 0, aligned: 0, perClass: Object.fromEntries(CLASS_NAMES.map((name) => [name, { tp: 0, fp: 0, fn: 0 }])) });
  const perClass = Object.fromEntries(CLASS_NAMES.map((name) => {
    const { tp, fp, fn } = classification.perClass[name];
    const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
    const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
    const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall);
    return [name, { tp, fp, fn, precision, recall, f1 }];
  }));
  const persianQuality = calculatePersianQuality(persianScores);
  const sourceTraceRate = metric(eligible === 0 ? null : traced / eligible, traced, eligible);
  const unsupportedAssumptionRate = metric(assumptions === 0 ? null : unsupported / assumptions, unsupported, assumptions);
  const classificationAccuracy = metric(classification.aligned === 0 ? null : classification.correct / classification.aligned, classification.correct, classification.aligned);
  const macroF1 = CLASS_NAMES.reduce((sum, name) => sum + perClass[name].f1, 0) / CLASS_NAMES.length;
  const firstPass = metric(evaluated.filter((item) => item.first_pass_valid).length / fixtures.length, evaluated.filter((item) => item.first_pass_valid).length, fixtures.length);
  const jsonValidity = metric(evaluated.filter((item) => item.json_valid).length / fixtures.length, evaluated.filter((item) => item.json_valid).length, fixtures.length);
  return {
    eval_set_id: EVAL_SET_ID,
    report_version: "1",
    provider_mode: provider.mode ?? "unknown",
    fixture_count: fixtures.length,
    metrics: {
      source_trace_rate: sourceTraceRate,
      unsupported_assumption_rate: unsupportedAssumptionRate,
      persian_quality: persianQuality,
      classification: {
        accuracy: classificationAccuracy,
        macro_f1: macroF1,
        per_class: perClass
      },
      first_pass_valid_rate: firstPass,
      json_validity_after_repair: jsonValidity
    },
    threshold_assessments: {
      source_trace_rate: assessThreshold(sourceTraceRate.value, thresholds.metrics.source_trace_rate),
      unsupported_assumption_rate: assessThreshold(unsupportedAssumptionRate.value, thresholds.metrics.unsupported_assumption_rate),
      persian_quality_raw_mean: assessThreshold(persianQuality.denominator === 0 ? null : persianQuality.numerator / persianQuality.denominator, thresholds.metrics.persian_quality_raw_mean),
      classification_macro_f1: assessThreshold(macroF1, thresholds.metrics.classification_macro_f1),
      first_pass_valid_rate: assessThreshold(firstPass.value, thresholds.metrics.first_pass_valid_rate),
      json_validity_after_repair: assessThreshold(jsonValidity.value, thresholds.metrics.json_validity_after_repair)
    },
    contract_gate: { status: evaluated.every((item) => item.failure_categories.length === 0) ? "pass" : "fail" },
    model_quality_gate: { status: "not_run", reason: "real_provider_and_human_review_required" },
    fixtures: evaluated.map(({ fixture_id, outcome, failure_categories }) => ({ fixture_id, outcome, failure_categories }))
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
