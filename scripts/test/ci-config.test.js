import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import test from "node:test";

const root = process.cwd();
const workflow = await readFile(path.join(root, ".github", "workflows", "ci.yml"), "utf8");
const pullRequestTemplate = await readFile(
  path.join(root, ".github", "pull_request_template.md"),
  "utf8"
);
const codeowners = await readFile(path.join(root, ".github", "CODEOWNERS"), "utf8");

test("CI runs documented quality and security gates on pull requests and main", () => {
  assert.match(workflow, /pull_request:\s*\n\s+branches: \[main\]/);
  assert.match(workflow, /push:\s*\n\s+branches: \[main\]/);
  assert.match(workflow, /name: Quality/);
  assert.match(workflow, /name: Security baseline/);
  assert.match(workflow, /npm run quality/);
  assert.match(workflow, /node scripts\/scan-secrets\.mjs/);
  assert.match(workflow, /node scripts\/scan-dependencies\.mjs/);
});

test("third-party actions are immutable and dependency caches are enabled", () => {
  const actionReferences = [...workflow.matchAll(/uses:\s+([^\s]+)@([^\s]+)/g)];
  assert.ok(actionReferences.length >= 6);
  for (const [, action, reference] of actionReferences) {
    assert.match(reference, /^[a-f0-9]{40}$/, `${action} must use a full commit SHA`);
  }
  assert.match(workflow, /cache: npm/);
  assert.match(workflow, /enable-cache: true/);
});

test("CI preserves quality and security evidence even after a failed gate", () => {
  assert.equal((workflow.match(/if: always\(\)/g) ?? []).length, 2);
  assert.match(workflow, /ci-quality-\$\{\{ github\.run_id \}\}/);
  assert.match(workflow, /ci-security-\$\{\{ github\.run_id \}\}/);
  assert.equal((workflow.match(/if-no-files-found: error/g) ?? []).length, 2);
});

test("pull request governance captures required review evidence and ownership", () => {
  for (const heading of [
    "Story / Issue",
    "Architecture impact",
    "Migration",
    "Security / Tenant impact",
    "Analytics / Observability",
    "Tests",
    "UI evidence",
    "Rollback / Recovery"
  ]) {
    assert.ok(pullRequestTemplate.includes(`## ${heading}`), `missing heading: ${heading}`);
  }
  assert.match(codeowners, /^\* @AlirezaJalili93$/m);
  assert.match(codeowners, /^\/apps\/api\/migrations\/ @AlirezaJalili93$/m);
  assert.match(codeowners, /^\/docs\/security\/ @AlirezaJalili93$/m);
});
