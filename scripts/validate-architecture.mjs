import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { validateDevelopmentRecords } from "./lib/development-records.mjs";

const root = process.cwd();
const failures = [];
const checks = [];
const skippedDirectories = new Set([
  ".git",
  ".data",
  ".next",
  ".mypy_cache",
  ".npm-cache",
  ".pip-cache",
  ".pytest_cache",
  ".ruff_cache",
  ".tools",
  ".venv",
  "__pycache__",
  "node_modules"
]);

function pass(message) {
  checks.push(message);
}

function fail(message) {
  failures.push(message);
}

async function exists(relativePath) {
  try {
    await access(path.join(root, relativePath));
    return true;
  } catch {
    return false;
  }
}

async function read(relativePath) {
  return readFile(path.join(root, relativePath), "utf8");
}

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(
    entries
      .filter((entry) => !skippedDirectories.has(entry.name))
      .map(async (entry) => {
        const fullPath = path.join(directory, entry.name);
        return entry.isDirectory() ? walk(fullPath) : [fullPath];
      })
  );
  return nested.flat();
}

const requiredPaths = [
  ".env.example",
  ".node-version",
  ".python-version",
  ".github/CODEOWNERS",
  ".github/pull_request_template.md",
  ".github/workflows/ci.yml",
  "README.md",
  "AGENTS.md",
  "apps/web/package.json",
  "apps/web/src/app/layout.tsx",
  "apps/api/pyproject.toml",
  "apps/api/app/main.py",
  "apps/worker/pyproject.toml",
  "apps/worker/app/main.py",
  "packages/ui/README.md",
  "packages/config/README.md",
  "packages/contracts/openapi.yaml",
  "packages/contracts/events.schema.json",
  "packages/design-tokens/tokens.json",
  "packages/design-tokens/tokens.css",
  "infra/compose.yaml",
  "evals/README.md",
  "tests/e2e/README.md",
  "docs/product/product-brief.md",
  "docs/architecture/system-architecture.md",
  "docs/architecture/data-model.md",
  "docs/security/threat-model.md",
  "docs/governance/document-driven-development.md",
  "docs/development/README.md",
  "docs/adr/ADR-004-stack-and-repository-bootstrap.md",
  "docs/adr/ADR-005-ci-baseline.md",
  "scripts/scan-dependencies.mjs",
  "scripts/scan-secrets.mjs",
  "design-system/MASTER.md"
];

for (const requiredPath of requiredPaths) {
  if (!(await exists(requiredPath))) fail(`Missing required architecture artifact: ${requiredPath}`);
}
if (!failures.some((item) => item.startsWith("Missing required"))) {
  pass("Architecture v2 repository skeleton exists");
}

if (await exists("packages/core/package.json")) {
  fail("Legacy JavaScript packages/core boundary must remain retired after ADR-004");
} else {
  pass("Legacy JavaScript domain package is retired");
}

const developmentRecordErrors = await validateDevelopmentRecords(root);
for (const error of developmentRecordErrors) fail(error);
if (developmentRecordErrors.length === 0) {
  pass("Every completed increment has linked development and passing test Markdown records");
}

for (const jsonPath of [
  "package.json",
  "apps/web/package.json",
  "packages/contracts/events.schema.json",
  "packages/design-tokens/tokens.json"
]) {
  try {
    JSON.parse(await read(jsonPath));
    pass(`${jsonPath} is valid JSON`);
  } catch (error) {
    fail(`${jsonPath} is invalid JSON: ${error.message}`);
  }
}

const webPackage = JSON.parse(await read("apps/web/package.json"));
for (const [group, dependencies] of Object.entries({
  dependencies: webPackage.dependencies,
  devDependencies: webPackage.devDependencies
})) {
  for (const [name, version] of Object.entries(dependencies ?? {})) {
    if (!/^(?:\d+\.\d+\.\d+|0\.1\.0)$/.test(version)) {
      fail(`${group} dependency ${name} must use an exact stable pin, found ${version}`);
    }
  }
}
if (!failures.some((item) => item.includes("exact stable pin"))) {
  pass("Direct web dependencies use exact stable pins");
}

for (const pyprojectPath of ["apps/api/pyproject.toml", "apps/worker/pyproject.toml"]) {
  const pyproject = await read(pyprojectPath);
  if (!pyproject.includes('requires-python = "==3.12.*"')) {
    fail(`${pyprojectPath} does not preserve the Python 3.12 baseline`);
  }
  if (/"[a-zA-Z0-9_-]+(?:\[[^\]]+\])?>=[^"]+"/.test(pyproject)) {
    fail(`${pyprojectPath} contains an unpinned direct dependency`);
  }
}
if (!failures.some((item) => item.includes("pyproject.toml"))) {
  pass("Python projects preserve 3.12 and exact direct dependency pins");
}

const nodeVersion = (await read(".node-version")).trim();
if (nodeVersion !== "24.11.1") {
  fail(`Node runtime must use the documented 24.11.1 pin, found ${nodeVersion}`);
} else {
  pass("Node runtime uses the documented exact pin");
}

const ciWorkflow = await read(".github/workflows/ci.yml");
for (const [name, pattern] of [
  ["pull request trigger", /pull_request:\s*\n\s+branches: \[main\]/],
  ["main push trigger", /push:\s*\n\s+branches: \[main\]/],
  ["quality gate", /npm run quality/],
  ["secret scan", /node scripts\/scan-secrets\.mjs/],
  ["dependency scan", /node scripts\/scan-dependencies\.mjs/],
  ["npm cache", /cache: npm/],
  ["uv cache", /enable-cache: true/]
]) {
  if (!pattern.test(ciWorkflow)) fail(`CI workflow is missing ${name}`);
}
const actionReferences = [...ciWorkflow.matchAll(/uses:\s+([^\s]+)@([^\s]+)/g)];
if (actionReferences.length === 0) fail("CI workflow contains no third-party action references");
for (const [, action, reference] of actionReferences) {
  if (!/^[a-f0-9]{40}$/.test(reference)) {
    fail(`CI third-party action ${action} must use an immutable commit SHA`);
  }
}
if ((ciWorkflow.match(/if: always\(\)/g) ?? []).length !== 2) {
  fail("CI workflow must preserve both quality and security artifacts on failure");
}
if (!failures.some((item) => item.startsWith("CI "))) {
  pass("CI workflow enforces pinned quality/security gates, caches, and failure artifacts");
}

const tokens = JSON.parse(await read("packages/design-tokens/tokens.json"));
for (const layer of ["primitive", "semantic", "component"]) {
  if (!tokens[layer] || typeof tokens[layer] !== "object") fail(`Token layer ${layer} is missing`);
}

function inspectReferences(node, prefix) {
  for (const [key, value] of Object.entries(node)) {
    const current = `${prefix}.${key}`;
    if (value && typeof value === "object" && "$value" in value) {
      if (prefix.startsWith("component") && !String(value.$value).startsWith("{")) {
        fail(`Component token ${current} must reference a primitive or semantic token`);
      }
      if (String(value.$value).startsWith("{")) {
        const reference = String(value.$value).slice(1, -1).split(".");
        let cursor = tokens;
        for (const part of reference) cursor = cursor?.[part];
        if (!cursor || !("$value" in cursor)) {
          fail(`Unresolved token reference ${value.$value} at ${current}`);
        }
      }
    } else if (value && typeof value === "object") {
      inspectReferences(value, current);
    }
  }
}
inspectReferences(tokens.semantic, "semantic");
inspectReferences(tokens.component, "component");
if (!failures.some((item) => /token/i.test(item))) {
  pass("Three-layer token references resolve and component tokens contain no raw values");
}

function hslToRgb(hsl) {
  let [hue, saturation, lightness] = hsl.split(/\s+/).map(Number.parseFloat);
  saturation /= 100;
  lightness /= 100;
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
  const x = chroma * (1 - Math.abs((hue / 60) % 2 - 1));
  const m = lightness - chroma / 2;
  let rgb;
  if (hue < 60) rgb = [chroma, x, 0];
  else if (hue < 120) rgb = [x, chroma, 0];
  else if (hue < 180) rgb = [0, chroma, x];
  else if (hue < 240) rgb = [0, x, chroma];
  else if (hue < 300) rgb = [x, 0, chroma];
  else rgb = [chroma, 0, x];
  return rgb.map((channel) => channel + m);
}

function relativeLuminance(hsl) {
  const [red, green, blue] = hslToRgb(hsl).map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  );
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrast(first, second) {
  const a = relativeLuminance(first);
  const b = relativeLuminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const colors = Object.fromEntries(
  Object.entries(tokens.primitive.color).map(([name, token]) => [name, token.$value])
);
const contrastPairs = [
  ["light body", colors.neutral900, colors.neutral50, 4.5],
  ["light muted", colors.neutral600, colors.neutral0, 4.5],
  ["light button", colors.neutral0, colors.indigo600, 4.5],
  ["dark body", colors.neutral50, colors.neutral900, 4.5],
  ["dark muted", colors.neutral200, colors.neutral800, 4.5],
  ["dark primary text", colors.indigo300, colors.neutral800, 4.5],
  ["dark danger text", colors.red400, colors.neutral800, 4.5]
];
for (const [name, foreground, background, minimum] of contrastPairs) {
  const ratio = contrast(foreground, background);
  if (ratio < minimum) fail(`${name} contrast ${ratio.toFixed(2)} is below ${minimum}:1`);
}
if (!failures.some((item) => item.includes("contrast"))) {
  pass("Core light/dark text pairs meet WCAG AA contrast");
}

const tokenCss = await read("packages/design-tokens/tokens.css");
const cssAfterPrimitive = tokenCss.split("/* Semantic: purpose aliases. */")[1] ?? "";
if (/#[0-9a-f]{3,8}\b|(?:rgb|hsl)a?\(\s*\d/i.test(cssAfterPrimitive)) {
  fail("Raw colors found after the primitive CSS section");
} else {
  pass("Semantic/component token CSS contains no raw colors");
}

const layout = await read("apps/web/src/app/layout.tsx");
const pageStyles = await read("apps/web/src/app/globals.css");
for (const [name, pattern, body] of [
  ["RTL root", /<html lang="fa" dir="rtl">/, layout],
  ["canonical token import", /@aria\/design-tokens\/tokens\.css/, layout],
  ["visible focus", /focus-visible/, pageStyles],
  ["reduced motion", /prefers-reduced-motion/, pageStyles]
]) {
  if (!pattern.test(body)) fail(`Web shell is missing ${name}`);
}
if (/#[0-9a-f]{3,8}\b|(?:rgb|hsl)a?\(\s*\d/i.test(pageStyles)) {
  fail("Web component CSS contains raw color values");
} else {
  pass("Web shell is RTL-first, accessible, reduced-motion aware and token-driven");
}

const allFiles = await walk(root);
const pythonFiles = allFiles.filter((file) => file.endsWith(".py"));
for (const file of pythonFiles) {
  const normalized = file.split(path.sep).join("/");
  const body = await readFile(file, "utf8");
  if (normalized.includes("/domain/") && /^(?:from|import)\s+(?:fastapi|pydantic|sqlalchemy|redis|supabase|openai)\b/m.test(body)) {
    fail(`Domain imports a framework/infrastructure SDK: ${path.relative(root, file)}`);
  }
  if (normalized.includes("/application/") && /^(?:from|import)\s+(?:openai|anthropic|google\.genai|supabase)\b/m.test(body)) {
    fail(`Application imports a provider SDK: ${path.relative(root, file)}`);
  }
}
if (!failures.some((item) => /Domain imports|Application imports/.test(item))) {
  pass("Python Domain/Application dependency boundaries are clean");
}

const apiPyproject = await read("apps/api/pyproject.toml");
const workerPyproject = await read("apps/worker/pyproject.toml");
if (/celery|dramatiq|\brq\b/i.test(`${apiPyproject}\n${workerPyproject}`)) {
  fail("Queue framework was selected before the required queue spike/ADR");
} else {
  pass("Worker bootstrap preserves the documented open queue decision");
}

const openApi = await read("packages/contracts/openapi.yaml");
if (!openApi.includes("- url: /api/v1")) fail("OpenAPI baseline must use /api/v1");
if (/workspaceId|\/v1\/generations/.test(openApi)) fail("Legacy API contract content remains active");
else pass("API contract baseline matches Architecture v2 naming and base path");

const eventContract = JSON.parse(await read("packages/contracts/events.schema.json"));
if (!eventContract.required.includes("accountId") || eventContract.required.includes("workspaceId")) {
  fail("Event envelope must use accountId as its tenant anchor");
} else {
  pass("Event envelope uses accountId as the tenant anchor");
}

const envExample = await read(".env.example");
for (const secretName of [
  "POSTGRES_PASSWORD",
  "DATABASE_URL",
  "REDIS_PASSWORD",
  "QUEUE_BROKER_URL",
  "STORAGE_ACCESS_KEY",
  "STORAGE_SECRET_KEY",
  "AI_PROVIDER_A_KEY",
  "AI_PROVIDER_B_KEY",
  "ANALYTICS_SERVER_KEY",
  "ERROR_TRACKING_DSN"
]) {
  const match = envExample.match(new RegExp(`^${secretName}=(.*)$`, "m"));
  if (!match || match[1].trim() !== "") fail(`${secretName} must exist and remain empty in .env.example`);
}
if (!failures.some((item) => item.includes(".env.example"))) {
  pass("Environment example contains required secret keys without secret values");
}

const compose = await read("infra/compose.yaml");
if (/^\s+-\s+"(?:0\.0\.0\.0:)?\d+:/m.test(compose)) {
  fail("Infrastructure exposes a service on all interfaces");
} else {
  pass("Local infrastructure ports bind to loopback only");
}

const markdownFiles = allFiles.filter((file) => file.endsWith(".md"));
for (const file of markdownFiles) {
  const body = await readFile(file, "utf8");
  const links = [...body.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)].map((match) => match[1]);
  for (const link of links) {
    if (/^(?:https?:|mailto:|#)/.test(link)) continue;
    const target = link.split("#")[0];
    if (!target) continue;
    try {
      await access(path.resolve(path.dirname(file), target));
    } catch {
      fail(`Broken local Markdown link in ${path.relative(root, file)}: ${link}`);
    }
  }
}
if (!failures.some((item) => item.startsWith("Broken local"))) {
  pass("Local Markdown links resolve");
}

for (const message of checks) console.log(`PASS  ${message}`);
for (const message of failures) console.error(`FAIL  ${message}`);

if (failures.length > 0) {
  console.error(`\nArchitecture validation failed with ${failures.length} issue(s).`);
  process.exitCode = 1;
} else {
  console.log(`\nArchitecture validation passed (${checks.length} checks).`);
}
