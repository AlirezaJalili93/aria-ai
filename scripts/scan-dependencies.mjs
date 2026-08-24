import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const reportDirectory = path.join(root, ".data", "ci");
const pipAuditVersion = process.env.PIP_AUDIT_VERSION ?? "2.10.1";
const defaultWindowsNpmCli = path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js");
const npmInvocation =
  process.platform === "win32"
    ? {
        command: process.execPath,
        prefix: [process.env.npm_execpath ?? defaultWindowsNpmCli]
      }
    : { command: "npm", prefix: [] };
const bundledUv = path.join(root, ".tools", "uv", "bin", process.platform === "win32" ? "uv.exe" : "uv");
const uvCommand = process.env.UV_PATH ?? (existsSync(bundledUv) ? bundledUv : "uv");
const log = [];
let failed = false;

await mkdir(reportDirectory, { recursive: true });

function run(label, command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: "utf8", env: process.env });
  const output = [result.stdout, result.stderr, result.error?.message].filter(Boolean).join("").trim();
  const status = result.status ?? 1;
  log.push(`## ${label}\nexit=${status}\n${output || "(no output)"}\n`);
  if (result.error || status !== 0) failed = true;
  return { ...result, output, status };
}

const npmAudit = run("npm audit", npmInvocation.command, [
  ...npmInvocation.prefix,
  "audit",
  "--audit-level=high",
  "--json"
]);
await writeFile(path.join(reportDirectory, "npm-audit.json"), `${npmAudit.stdout || "{}"}\n`, "utf8");

for (const project of ["api", "worker"]) {
  const requirementsPath = path.join(reportDirectory, `${project}-requirements.txt`);
  const exportResult = run(`uv export (${project})`, uvCommand, [
    "export",
    "--quiet",
    "--project",
    `apps/${project}`,
    "--locked",
    "--all-groups",
    "--no-emit-local",
    "--format",
    "requirements-txt",
    "--output-file",
    requirementsPath
  ]);

  if (exportResult.status === 0 && !exportResult.error) {
    run(`pip-audit (${project})`, uvCommand, [
      "tool",
      "run",
      "--from",
      `pip-audit==${pipAuditVersion}`,
      "pip-audit",
      "--requirement",
      requirementsPath,
      "--strict",
      "--no-deps",
      "--disable-pip",
      "--progress-spinner",
      "off",
      "--format",
      "json",
      "--output",
      path.join(reportDirectory, `${project}-pip-audit.json`)
    ]);
  }
}

await writeFile(path.join(reportDirectory, "dependency-scan.log"), `${log.join("\n")}\n`, "utf8");

if (failed) {
  console.error(`FAIL  Dependency scan failed; inspect ${path.relative(root, reportDirectory)}`);
  process.exitCode = 1;
} else {
  console.log("PASS  npm, API, and worker dependency scans found no blocking vulnerabilities");
}
