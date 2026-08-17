import { readFileSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const privateKeyMarker = ["-----BEGIN ", "(?:RSA|EC|OPENSSH|DSA)? ?PRIVATE KEY-----"].join("");

const detectors = [
  { name: "private-key", pattern: new RegExp(privateKeyMarker) },
  { name: "github-token", pattern: /\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b/ },
  { name: "openai-token", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/ },
  { name: "aws-access-key", pattern: /\bAKIA[A-Z0-9]{16}\b/ },
  { name: "google-api-key", pattern: /\bAIza[A-Za-z0-9_-]{30,}\b/ },
  {
    name: "credentialed-database-url",
    pattern: /\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?):\/\/[^\s:@/]+:[^\s@/]+@/i
  },
  {
    name: "nonempty-sensitive-environment-value",
    pattern: /^\s*[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|ACCESS_KEY|PRIVATE_KEY)\s*=\s*[^\s#][^\r\n]*$/m
  }
];

export function scanContent(relativePath, content) {
  const findings = [];
  const lines = content.split(/\r?\n/);

  for (const detector of detectors) {
    for (const [index, line] of lines.entries()) {
      detector.pattern.lastIndex = 0;
      if (detector.pattern.test(line)) {
        findings.push({ detector: detector.name, path: relativePath, line: index + 1 });
      }
    }
  }

  return findings;
}

export function scanPublishableFiles(root) {
  const listed = spawnSync(
    "git",
    ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    { cwd: root, encoding: "utf8" }
  );

  if (listed.error || listed.status !== 0) {
    throw new Error(listed.error?.message ?? listed.stderr.trim() ?? "git ls-files failed");
  }

  const files = listed.stdout.split("\0").filter(Boolean);
  const findings = [];
  let filesScanned = 0;

  for (const relativePath of files) {
    const buffer = readFileSync(path.join(root, relativePath));
    if (buffer.includes(0)) continue;
    filesScanned += 1;
    findings.push(...scanContent(relativePath.replaceAll("\\", "/"), buffer.toString("utf8")));
  }

  return { filesScanned, findings };
}
