import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const workspaceUv = path.join(
  process.cwd(),
  ".tools",
  "uv",
  "bin",
  process.platform === "win32" ? "uv.exe" : "uv"
);
const uv = process.env.UV_PATH || (existsSync(workspaceUv) ? workspaceUv : "uv");
const result = spawnSync(uv, process.argv.slice(2), {
  cwd: process.cwd(),
  env: process.env,
  stdio: "inherit",
  shell: false
});

if (result.error) {
  console.error(`Unable to execute uv: ${result.error.message}`);
  console.error("Install uv 0.12.5 or set UV_PATH to its executable.");
  process.exit(1);
}

process.exit(result.status ?? 1);
