import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const runnerPath = "scripts/generated-runtime-security/run-security-review.mjs";
const browserPath = "scripts/generated-runtime-security/browser-cdp.mjs";
const corpusPath =
  "evals/generation-output/security/generated_runtime_security_v1/adversarial-corpus.json";

test("0098 uses the exact 0097 prototype boundary and records reproducibility identities", async () => {
  const source = await readFile(runnerPath, "utf8");
  assert.match(source, /from "\.\.\/generation-exportability\/prototype\.mjs"/);
  assert.match(source, /PROTOTYPE_DEPENDENCIES/);
  assert.match(source, /package_lock_hash/);
  assert.match(source, /static_artifact_hash/);
  assert.match(source, /renderer_version/);
  assert.match(source, /registry_version/);
  assert.match(source, /ast_schema_version/);
  assert.match(source, /fixture_version/);
  assert.match(source, /security_suite_version/);
});

test("0098 adversarial corpus covers inert markup and fail-closed contract boundaries", async () => {
  const corpus = JSON.parse(await readFile(corpusPath, "utf8"));
  assert.equal(corpus.suite_version, "generated_runtime_security_v1");
  assert.equal(corpus.fixture_version, "generation_ast_v1");
  assert.deepEqual(
    new Set(corpus.cases.map((item) => item.case_id)),
    new Set([
      "ast_text_markup_inert",
      "ast_unknown_component",
      "ast_unknown_property",
      "ast_javascript_navigation",
      "ast_remote_asset",
      "ast_data_asset",
      "ast_path_traversal",
      "ast_provider_owned_protection"
    ])
  );
  assert.equal(corpus.cases.filter((item) => item.expected === "accepted_as_inert_text").length, 1);
  assert.equal(corpus.cases.filter((item) => item.expected === "rejected").length, 7);
});

test("0098 Browser Gate observes and blocks non-static runtime requests", async () => {
  const source = await readFile(browserPath, "utf8");
  assert.match(source, /Fetch\.enable/);
  assert.match(source, /Fetch\.failRequest/);
  assert.match(source, /Network\.webSocketCreated/);
  assert.match(source, /Network\.clearBrowserCookies/);
  assert.match(source, /authorization/);
  assert.match(source, /cookie/);
  assert.match(source, /apiDenied/);
  assert.match(source, /imageAllowed/);
  assert.match(source, /0098_NETWORK_BLOCK_CONTROL_FAILED/);
  assert.doesNotMatch(source, /startsWith\(['"]https:\/\/trusted/);
});

test("0098 enforces read-only serving, dependency policy and bounded Artifact scans", async () => {
  const source = await readFile(runnerPath, "utf8");
  assert.match(source, /request\.method !== "GET" && request\.method !== "HEAD"/);
  assert.match(source, /0098_READ_ONLY_CONTROL_FAILED/);
  assert.match(source, /--ignore-scripts/);
  assert.match(source, /--audit-level=high/);
  assert.match(source, /vulnerabilities\.high/);
  assert.match(source, /vulnerabilities\.critical/);
  assert.match(source, /generated_executable_sinks/);
  assert.match(source, /source_maps/);
  assert.match(source, /repository_path_leaks/);
});

test("0098 evidence separates synthetic results from production Preview security", async () => {
  const source = await readFile(runnerPath, "utf8");
  assert.match(source, /static_artifact_security: "PASS"/);
  assert.match(source, /synthetic_runtime_behavior: "PASS"/);
  assert.match(source, /production_preview_security: "NOT_EVALUATED"/);
  assert.match(source, /await rm\(runRoot, \{ recursive: true, force: true \}\)/);
  assert.doesNotMatch(source, /customer[_ -]?content/i);
});
