import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { validateDevelopmentRecords } from "../lib/development-records.mjs";

const validDevelopment = `# Development Record: Example

[Test report](./test-report.md)

## Scope
Scope.
## Source Documents
User request and AGENTS.md.
## Requirement Traceability
| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-001 | User request | file.js | TC-001 |
## Assumptions and Clarifications
**Unapproved assumptions:** None
## Changes
Changes.
## Structure Preservation
Preserved.
## Senior Review
Reviewed.
## Verification
Verified.
## Remaining Risks
None.
`;

const validTestReport = `# Test Report: Example

[Development record](./development.md)

## Environment
Node.
## Test Cases
| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-001 | Unit | Example | Pass |
## Execution Results
| ID | Command | Actual | Status |
|---|---|---|---|
| TC-001 | npm test | Pass | PASS |
## Final Status
**Final status:** PASS
`;

async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(), "aria-doc-records-"));
  const record = path.join(root, "docs", "development", "0001-example");
  await mkdir(record, { recursive: true });
  return { root, record };
}

test("accepts a complete linked development and test record", async (context) => {
  const { root, record } = await fixture();
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(record, "development.md"), validDevelopment);
  await writeFile(path.join(record, "test-report.md"), validTestReport);
  assert.deepEqual(await validateDevelopmentRecords(root), []);
});

test("rejects a completed increment without a test report", async (context) => {
  const { root, record } = await fixture();
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(record, "development.md"), validDevelopment);
  assert.deepEqual(await validateDevelopmentRecords(root), ["0001-example is missing test-report.md"]);
});

test("rejects pending final status", async (context) => {
  const { root, record } = await fixture();
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(record, "development.md"), validDevelopment);
  await writeFile(
    path.join(record, "test-report.md"),
    validTestReport.replace("**Final status:** PASS", "**Final status:** PENDING")
  );
  assert.deepEqual(await validateDevelopmentRecords(root), [
    "0001-example/test-report.md final status is not PASS"
  ]);
});

test("rejects a development record without requirement traceability", async (context) => {
  const { root, record } = await fixture();
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(
    path.join(record, "development.md"),
    validDevelopment.replace("| REQ-001 | User request | file.js | TC-001 |", "No requirement rows.")
  );
  await writeFile(path.join(record, "test-report.md"), validTestReport);
  assert.deepEqual(await validateDevelopmentRecords(root), [
    "0001-example/development.md contains no requirement traceability IDs"
  ]);
});

test("rejects a development record missing structure preservation evidence", async (context) => {
  const { root, record } = await fixture();
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(
    path.join(record, "development.md"),
    validDevelopment.replace("## Structure Preservation", "## Removed Structure Section")
  );
  await writeFile(path.join(record, "test-report.md"), validTestReport);
  assert.deepEqual(await validateDevelopmentRecords(root), [
    "0001-example/development.md is missing ## Structure Preservation"
  ]);
});

test("rejects unapproved assumptions", async (context) => {
  const { root, record } = await fixture();
  context.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(
    path.join(record, "development.md"),
    validDevelopment.replace("**Unapproved assumptions:** None", "**Unapproved assumptions:** One")
  );
  await writeFile(path.join(record, "test-report.md"), validTestReport);
  assert.deepEqual(await validateDevelopmentRecords(root), [
    "0001-example/development.md has unapproved or undocumented assumptions"
  ]);
});
