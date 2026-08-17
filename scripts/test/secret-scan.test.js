import assert from "node:assert/strict";
import test from "node:test";
import { scanContent } from "../lib/secret-scan.mjs";

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
