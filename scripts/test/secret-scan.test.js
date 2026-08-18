import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { scanContent, scanPublishableFiles } from "../lib/secret-scan.mjs";

test("accepts documented empty secret placeholders", () => {
  const content = "DATABASE_URL=\nAPI_TOKEN=\nPASSWORD=   # provided locally\n";
  assert.deepEqual(scanContent(".env.example", content), []);
});

test("detects token and private-key material without returning secret values", () => {
  const token = ["ghp", "_", "A".repeat(36)].join("");
  const privateKey = ["-----BEGIN ", "PRIVATE KEY-----"].join("");
  const findings = scanContent("unsafe.env", `${token}\n${privateKey}\n`);

  assert.deepEqual(
    findings.map(({ detector, line }) => ({ detector, line })),
    [
      { detector: "private-key", line: 2 },
      { detector: "github-token", line: 1 }
    ]
  );
  assert.equal(JSON.stringify(findings).includes(token), false);
});

test("detects credentialed database URLs and nonempty sensitive environment values", () => {
  const credentialedUrl = ["postgresql", "://", "aria", ":", "password", "@db.local/app"].join("");
  const content = `DATABASE_URL=${credentialedUrl}\nSERVICE_TOKEN=not-empty\n`;
  const detectors = scanContent("unsafe.env", content).map(({ detector }) => detector);

  assert.deepEqual(detectors, [
    "credentialed-database-url",
    "nonempty-sensitive-environment-value"
  ]);
});

test("skips tracked files deleted by an in-progress migration", async (context) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "aria-secret-scan-"));
  const deletedPath = path.join(root, "superseded-config.yml");
  context.after(() => rm(root, { recursive: true, force: true }));

  assert.equal(spawnSync("git", ["init", "-q"], { cwd: root }).status, 0);
  await writeFile(deletedPath, "safe: true\n", "utf8");
  assert.equal(spawnSync("git", ["add", "superseded-config.yml"], { cwd: root }).status, 0);
  await rm(deletedPath);

  assert.deepEqual(scanPublishableFiles(root), { filesScanned: 0, findings: [] });
});
