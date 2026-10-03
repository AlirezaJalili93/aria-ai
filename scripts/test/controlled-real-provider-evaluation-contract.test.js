import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

test("0086 freezes the exact matrix and fail-closed numeric caps", () => {
  const adr = read("docs/adr/ADR-072-controlled-real-provider-quality-evaluation.md");
  const harness = read("apps/worker/app/application/provider_quality_evaluation.py");

  assert.match(adr, /Status: Accepted/);
  assert.match(adr, /max_total_invocations\s+= 120/);
  assert.match(adr, /max_serialized_request_utf8_bytes\s+= 8_000/);
  assert.match(adr, /max_output_tokens_per_invocation\s+= 25_000/);
  assert.match(adr, /max_total_estimated_budget\s+= USD 25\.00/);

  assert.match(harness, /FIXTURES_PER_CANDIDATE = 60/);
  assert.match(harness, /MAX_TOTAL_INVOCATIONS = 120/);
  assert.match(harness, /MAX_SERIALIZED_INPUT_BYTES = 8_000/);
  assert.match(harness, /MAX_OUTPUT_TOKENS = 25_000/);
  assert.match(harness, /MAX_TOTAL_BUDGET = Decimal\("25\.00"\)/);
});

test("0086 sends the frozen reasoning and output ceilings to both providers", () => {
  const openai = read("apps/worker/app/infrastructure/ai/openai_responses.py");
  const gemini = read("apps/worker/app/infrastructure/ai/gemini_generate_content.py");

  assert.match(openai, /max_output_tokens=25_000/);
  assert.match(openai, /reasoning=\{"mode": "standard", "effort": "medium"\}/);
  assert.match(gemini, /max_output_tokens=25_000/);
  assert.match(gemini, /ThinkingConfig\([\s\S]*thinking_level=types\.ThinkingLevel\.MEDIUM/);
});

test("0086 has no retry, repair, fallback, hosted, or automatic promotion path", () => {
  const harness = read("apps/worker/app/application/provider_quality_evaluation.py");

  assert.match(harness, /MAX_INVOCATIONS_PER_CASE = 1/);
  assert.match(harness, /technical_retry:\s*int\s*=\s*0/);
  assert.match(harness, /semantic_repair:\s*int\s*=\s*0/);
  assert.match(harness, /fallback:\s*int\s*=\s*0/);
  assert.match(harness, /hosted_execution:\s*bool\s*=\s*False/);
  assert.match(harness, /automatic_promotion:\s*bool\s*=\s*False/);
  assert.match(harness, /customer_content:\s*bool\s*=\s*False/);
});

test("0086 keeps synthetic review material local and outside tracked evidence", () => {
  const ignore = read(".gitignore");
  const adr = read("docs/adr/ADR-072-controlled-real-provider-quality-evaluation.md");

  assert.match(ignore, /^\.local\/eval-review-bundles\/$/m);
  assert.match(adr, /deleted after adjudicated scores/i);
  assert.match(adr, /contains synthetic data only/i);
  assert.match(adr, /no prompt, raw response,\s*fixture content, generated content/i);
});

test("0086 freezes distinct uncontaminated prompt and output-schema packages", () => {
  const promptPackage = read(
    "apps/worker/app/infrastructure/ai/provider_quality_prompt_package.py",
  );
  const fixtures = read(
    "apps/worker/app/infrastructure/ai/provider_quality_fixtures.py",
  );

  assert.match(promptPackage, /ai-01-real-eval-prompt-v1/);
  assert.match(promptPackage, /ai-02-real-eval-prompt-v1/);
  assert.match(promptPackage, /ai-03-real-eval-prompt-v1/);
  assert.match(promptPackage, /candidate-context-batch-v1/);
  assert.match(promptPackage, /candidate-requirement-batch-v1/);
  assert.match(promptPackage, /candidate-gap-batch-rule-signals-v1/);
  assert.match(promptPackage, /provider_critical_classification_prohibited/);
  assert.match(promptPackage, /VersionedCriticalGapRuleEvaluator/);
  assert.match(fixtures, /customer_content_prohibited/);
});

test("0086 normalizes every successful Provider output before evaluation evidence", () => {
  const harness = read("apps/worker/app/application/provider_quality_evaluation.py");

  assert.match(harness, /class EvaluationOutputNormalizer/);
  assert.match(harness, /await self\._output_normalizer\.normalize/);
  assert.match(harness, /failure_class="invalid_response"/);
  assert.doesNotMatch(harness, /normalized_output=result\.data/);
});

test("0086 real wiring is manual-only and retains the existing single Usage writer", () => {
  const runtime = read("apps/worker/app/runtime/provider_quality_evaluation.py");

  assert.match(runtime, /FailureCoordinatorSingleInvocation/);
  assert.match(runtime, /EVALUATION_INVOCATION_POLICY/);
  assert.match(runtime, /role": "aria_worker"/);
  assert.match(runtime, /ApprovedCandidateModelPreflight/);
  assert.match(runtime, /PostgresProviderPriceCatalog/);
  assert.match(runtime, /SqlAlchemyUsageLedger/);
  assert.doesNotMatch(runtime, /if __name__ == ["']__main__["']/);
});

test("0086 imports adjudicated review evidence through the frozen safe comparison boundary", () => {
  const comparison = read("scripts/provider-quality-comparison.mjs");
  const schemaText = read("evals/provider-quality-evaluation/review-import.schema.json");
  const schema = JSON.parse(schemaText);

  assert.match(comparison, /provider-quality-human-review-v1/);
  assert.match(comparison, /percentileNearestRank/);
  assert.match(comparison, /calculateRequirementReview/);
  assert.match(comparison, /calculateGapReview/);
  assert.equal(schema.properties.review_version.const, "provider-quality-human-review-v1");
  assert.match(schemaText, /reviewer_id/);
  assert.doesNotMatch(schemaText, /free[_-]?text|notes/i);
});
