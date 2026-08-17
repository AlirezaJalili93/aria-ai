import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";

const DEVELOPMENT_HEADINGS = [
  "## Scope",
  "## Source Documents",
  "## Requirement Traceability",
  "## Assumptions and Clarifications",
  "## Changes",
  "## Structure Preservation",
  "## Senior Review",
  "## Verification",
  "## Remaining Risks"
];

const TEST_HEADINGS = [
  "## Environment",
  "## Test Cases",
  "## Execution Results",
  "## Final Status"
];

async function fileExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function validateDevelopmentRecords(root) {
  const recordsRoot = path.join(root, "docs", "development");
  const errors = [];
  let entries;

  try {
    entries = await readdir(recordsRoot, { withFileTypes: true });
  } catch {
    return ["Missing docs/development directory"];
  }

  const recordDirectories = entries.filter(
    (entry) => entry.isDirectory() && !entry.name.startsWith("_")
  );
  if (recordDirectories.length === 0) return ["No completed development records found"];

  for (const entry of recordDirectories) {
    if (!/^\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(entry.name)) {
      errors.push(`Invalid development increment ID: ${entry.name}`);
      continue;
    }

    const recordRoot = path.join(recordsRoot, entry.name);
    const developmentPath = path.join(recordRoot, "development.md");
    const testReportPath = path.join(recordRoot, "test-report.md");

    if (!(await fileExists(developmentPath))) {
      errors.push(`${entry.name} is missing development.md`);
      continue;
    }
    if (!(await fileExists(testReportPath))) {
      errors.push(`${entry.name} is missing test-report.md`);
      continue;
    }

    const development = await readFile(developmentPath, "utf8");
    const testReport = await readFile(testReportPath, "utf8");

    if (!development.startsWith("# Development Record:")) {
      errors.push(`${entry.name}/development.md has an invalid title`);
    }
    if (!testReport.startsWith("# Test Report:")) {
      errors.push(`${entry.name}/test-report.md has an invalid title`);
    }
    for (const heading of DEVELOPMENT_HEADINGS) {
      if (!development.includes(heading)) errors.push(`${entry.name}/development.md is missing ${heading}`);
    }
    for (const heading of TEST_HEADINGS) {
      if (!testReport.includes(heading)) errors.push(`${entry.name}/test-report.md is missing ${heading}`);
    }
    if (!development.includes("(./test-report.md)")) {
      errors.push(`${entry.name}/development.md does not link to test-report.md`);
    }
    if (!testReport.includes("(./development.md)")) {
      errors.push(`${entry.name}/test-report.md does not link to development.md`);
    }
    if (!/\|\s*TC-\d+/i.test(testReport)) {
      errors.push(`${entry.name}/test-report.md contains no test case IDs`);
    }
    if (!/\|\s*REQ-\d+\s*\|/i.test(development)) {
      errors.push(`${entry.name}/development.md contains no requirement traceability IDs`);
    }
    if (!development.includes("**Unapproved assumptions:** None")) {
      errors.push(`${entry.name}/development.md has unapproved or undocumented assumptions`);
    }
    if (!testReport.includes("**Final status:** PASS")) {
      errors.push(`${entry.name}/test-report.md final status is not PASS`);
    }
  }

  return errors;
}
