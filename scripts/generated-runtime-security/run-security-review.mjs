import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile
} from "node:fs/promises";
import { createServer } from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

import {
  PROTOTYPE_DEPENDENCIES,
  readSyntheticCandidate,
  writePrototype
} from "../generation-exportability/prototype.mjs";
import { runBrowserSecurityGate } from "./browser-cdp.mjs";

export const SECURITY_SUITE_VERSION = "generated_runtime_security_v1";
export const REGISTRY_VERSION = "component_registry_v1";
export const AST_SCHEMA_VERSION = "generation_ast_schema_v1";
export const FIXTURE_VERSION = "generation_ast_v1";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "..", "..");
const evidencePath = path.join(
  repositoryRoot,
  "docs",
  "development",
  "0098-generated-runtime-security-review",
  "security-evidence.json"
);
const fixtureRoot = path.join(
  repositoryRoot,
  "evals",
  "generation-output",
  "fixtures",
  FIXTURE_VERSION
);
const fixtureNames = [
  "fa_gen_landing_001.json",
  "fa_gen_corporate_001.json",
  "fa_gen_portfolio_001.json"
];
const corpusPath = path.join(
  repositoryRoot,
  "evals",
  "generation-output",
  "security",
  SECURITY_SUITE_VERSION,
  "adversarial-corpus.json"
);
const npmExecutable = process.platform === "win32" ? "npm.cmd" : "npm";
const npmCli = process.env.npm_execpath;

function safeEnvironment(tempRoot) {
  const allowed = [
    "PATH",
    "Path",
    "SystemRoot",
    "WINDIR",
    "ComSpec",
    "PATHEXT",
    "TEMP",
    "TMP",
    "LOCALAPPDATA",
    "APPDATA",
    "USERPROFILE",
    "HOME",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "ARIA_0098_BROWSER_PATH"
  ];
  const environment = Object.fromEntries(
    allowed.filter((name) => process.env[name] !== undefined).map((name) => [name, process.env[name]])
  );
  return {
    ...environment,
    NEXT_TELEMETRY_DISABLED: "1",
    npm_config_audit: "false",
    npm_config_fund: "false",
    npm_config_update_notifier: "false",
    TMP: tempRoot,
    TEMP: tempRoot
  };
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? repositoryRoot,
    env: options.env ?? process.env,
    encoding: "utf8",
    stdio: options.capture ? "pipe" : "inherit",
    windowsHide: true
  });
  if (result.error || (!options.allowedStatuses?.includes(result.status) && result.status !== 0)) {
    const detail = options.capture ? `\n${result.stdout ?? ""}\n${result.stderr ?? ""}` : "";
    const cause = result.error ? ` (${result.error.message})` : "";
    throw new Error(`0098_COMMAND_FAILED: ${command} ${args.join(" ")}${cause}${detail}`);
  }
  return { status: result.status, stdout: (result.stdout ?? "").trim(), stderr: (result.stderr ?? "").trim() };
}

function runNpm(args, options = {}) {
  if (npmCli) return run(process.execPath, [npmCli, ...args], options);
  return run(npmExecutable, args, options);
}

async function sha256File(filePath) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(filePath)) hash.update(chunk);
  return hash.digest("hex");
}

async function listFiles(root) {
  const result = [];
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) await visit(absolute);
      else result.push(absolute);
    }
  }
  await visit(root);
  return result.sort((first, second) => first.localeCompare(second));
}

async function sha256Tree(root) {
  const hash = createHash("sha256");
  for (const file of await listFiles(root)) {
    hash.update(path.relative(root, file).replaceAll("\\", "/"));
    hash.update("\0");
    for await (const chunk of createReadStream(file)) hash.update(chunk);
    hash.update("\0");
  }
  return hash.digest("hex");
}

async function packLocalPackage(packageDirectory, destination, stableName) {
  const before = new Set(await readdir(destination));
  runNpm(["pack", "--pack-destination", destination, "--silent"], { cwd: packageDirectory });
  const created = (await readdir(destination)).filter((name) => !before.has(name) && name.endsWith(".tgz"));
  if (created.length !== 1) throw new Error("0098_TARBALL_CREATION_FAILED");
  const finalPath = path.join(destination, stableName);
  await rename(path.join(destination, created[0]), finalPath);
  return finalPath;
}

function assertPortableLockfile(lockText) {
  const normalizedRepository = repositoryRoot.replaceAll("\\", "/").toLowerCase();
  const normalizedLock = lockText.replaceAll("\\", "/").toLowerCase();
  if (normalizedLock.includes(normalizedRepository) || /workspace:|file:\.\.\//i.test(lockText)) {
    throw new Error("0098_NON_PORTABLE_LOCKFILE");
  }
  if (!lockText.includes("file:vendor/generation-renderer.tgz") || !lockText.includes("file:vendor/design-tokens.tgz")) {
    throw new Error("0098_VENDOR_TARBALLS_NOT_LOCKED");
  }
  if (/"(?:openai|@google\/genai|@anthropic-ai\/sdk)"\s*:/i.test(lockText)) {
    throw new Error("0098_PROVIDER_DEPENDENCY_PROHIBITED");
  }
}

function contentType(filePath) {
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  if (filePath.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

export async function withReadOnlyStaticServer(outputRoot, callback) {
  let rejectedWrites = 0;
  const server = createServer(async (request, response) => {
    if (request.method !== "GET" && request.method !== "HEAD") {
      rejectedWrites += 1;
      response.writeHead(405, { Allow: "GET, HEAD", "Cache-Control": "no-store" }).end();
      return;
    }
    try {
      const requestPath = decodeURIComponent(new URL(request.url ?? "/", "http://127.0.0.1").pathname);
      const relative = requestPath.endsWith("/") || path.extname(requestPath) === ""
        ? path.join(requestPath.slice(1), "index.html")
        : requestPath.slice(1);
      const root = path.resolve(outputRoot);
      const resolved = path.resolve(root, relative || "index.html");
      if (!resolved.startsWith(`${root}${path.sep}`) && resolved !== path.join(root, "index.html")) {
        response.writeHead(404).end();
        return;
      }
      const metadata = await stat(resolved);
      if (!metadata.isFile()) throw new Error("not a file");
      response.writeHead(200, {
        "Cache-Control": "no-store",
        "Content-Type": contentType(resolved),
        "X-Content-Type-Options": "nosniff"
      });
      if (request.method === "HEAD") response.end();
      else createReadStream(resolved).pipe(response);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("0098_STATIC_SERVER_FAILED");
    const origin = `http://127.0.0.1:${address.port}`;
    const writeProbe = await fetch(`${origin}/__write_probe`, { method: "POST", body: "synthetic" });
    if (writeProbe.status !== 405 || rejectedWrites !== 1) throw new Error("0098_READ_ONLY_CONTROL_FAILED");
    return await callback({ origin, readOnlyProbe: "PASS" });
  } finally {
    await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
  }
}

async function scanArtifact({ prototypeRoot, outputRoot }) {
  const outputFiles = await listFiles(outputRoot);
  const sourceFiles = await listFiles(path.join(prototypeRoot, "app"));
  const textFiles = outputFiles.filter((file) => /\.(?:html|css|js|json|txt|svg)$/i.test(file));
  const findings = {
    active_external_references: [],
    secret_markers: [],
    repository_path_leaks: [],
    source_maps: outputFiles.filter((file) => file.endsWith(".map")).map((file) => path.relative(outputRoot, file)),
    generated_executable_sinks: []
  };
  const secretPattern = /OPENAI_API_KEY|GEMINI_API_KEY|DATABASE_URL|SUPABASE_SERVICE_ROLE|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY/i;
  const normalizedRepository = repositoryRoot.replaceAll("\\", "/").toLowerCase();
  for (const file of textFiles) {
    const content = await readFile(file, "utf8");
    const activePattern = file.endsWith(".html")
      ? /(?:src|href|action)=["'](?:https?:|data:|blob:|javascript:)/gi
      : file.endsWith(".css")
        ? /url\(\s*["']?(?:https?:|data:|blob:|javascript:)/gi
        : null;
    if (activePattern?.test(content)) findings.active_external_references.push(path.relative(outputRoot, file));
    if (secretPattern.test(content)) findings.secret_markers.push(path.relative(outputRoot, file));
    if (content.replaceAll("\\", "/").toLowerCase().includes(normalizedRepository)) {
      findings.repository_path_leaks.push(path.relative(outputRoot, file));
    }
  }
  const sinkPattern = /dangerouslySetInnerHTML|\beval\s*\(|\bnew\s+Function\s*\(|\bdocument\.write\s*\(|\bimport\s*\(/;
  for (const file of sourceFiles) {
    const content = await readFile(file, "utf8");
    if (sinkPattern.test(content)) findings.generated_executable_sinks.push(path.relative(prototypeRoot, file));
  }
  for (const value of Object.values(findings)) value.sort();
  if (Object.values(findings).some((value) => value.length > 0)) {
    throw new Error("0098_STATIC_ARTIFACT_SECURITY_FAILED");
  }
  return findings;
}

function createAdversarialCandidate(candidate, corpus) {
  const result = structuredClone(candidate);
  const testCase = corpus.cases.find((item) => item.case_id === "ast_text_markup_inert");
  const hero = result.pages.flatMap((page) => page.sections).find((section) => section.component_type === "Hero");
  if (!hero || !testCase) throw new Error("0098_ADVERSARIAL_FIXTURE_INVALID");
  hero.content.heading = testCase.value;
  return result;
}

async function buildAndReview({
  runRoot,
  name,
  candidate,
  fixtureId,
  rendererTarball,
  tokensTarball,
  environment
}) {
  const prototypeRoot = path.join(runRoot, name);
  const ast = await writePrototype({ prototypeRoot, candidate, rendererTarball, tokensTarball });
  runNpm(["install", "--package-lock-only", "--ignore-scripts"], { cwd: prototypeRoot, env: environment });
  const lockPath = path.join(prototypeRoot, "package-lock.json");
  const lockText = await readFile(lockPath, "utf8");
  assertPortableLockfile(lockText);
  runNpm(["ci", "--ignore-scripts"], { cwd: prototypeRoot, env: environment });
  const auditRun = runNpm(["audit", "--omit=dev", "--audit-level=high", "--json"], {
    cwd: prototypeRoot,
    env: environment,
    capture: true,
    allowedStatuses: [0, 1]
  });
  const audit = JSON.parse(auditRun.stdout);
  const vulnerabilities = audit.metadata?.vulnerabilities ?? {};
  if ((vulnerabilities.high ?? 0) > 0 || (vulnerabilities.critical ?? 0) > 0) {
    throw new Error("0098_DEPENDENCY_SECURITY_BLOCKER");
  }
  runNpm(["run", "build"], { cwd: prototypeRoot, env: environment });
  const outputRoot = path.join(prototypeRoot, "out");
  const staticScan = await scanArtifact({ prototypeRoot, outputRoot });
  const browser = await withReadOnlyStaticServer(outputRoot, async ({ origin, readOnlyProbe }) => ({
    read_only_probe: readOnlyProbe,
    ...(await runBrowserSecurityGate({
      origin,
      pagePaths: ast.pages.map((page) => page.path),
      profileRoot: path.join(runRoot, `${name}-browser-profile`)
    }))
  }));
  return {
    project_type: ast.project_type,
    fixture_id: fixtureId,
    adversarial: name === "landing-adversarial",
    renderer_version: "0.1.0",
    registry_version: REGISTRY_VERSION,
    ast_schema_version: AST_SCHEMA_VERSION,
    fixture_version: FIXTURE_VERSION,
    package_lock_hash: await sha256File(lockPath),
    static_artifact_hash: await sha256Tree(outputRoot),
    dependency_scan: { status: "PASS", vulnerabilities },
    static_scan: { status: "PASS", ...staticScan },
    runtime: { status: "PASS", ...browser }
  };
}

async function main() {
  const runRoot = path.join(os.tmpdir(), `aria-0098-${randomUUID()}`);
  const tarballRoot = path.join(runRoot, "tarballs");
  await mkdir(tarballRoot, { recursive: true });
  const evidence = {
    increment: "0098-generated-runtime-security-review",
    security_suite_version: SECURITY_SUITE_VERSION,
    status: "PASS",
    gates: {
      static_artifact_security: "PASS",
      synthetic_runtime_behavior: "PASS",
      production_preview_security: "NOT_EVALUATED"
    },
    runtime: { node: process.version, npm: "11.6.2", next: PROTOTYPE_DEPENDENCIES.next },
    packages: {},
    candidates: [],
    findings: [],
    cleanup: "completed"
  };
  try {
    runNpm(["run", "build", "--workspace", "@aria/generation-renderer"]);
    const rendererTarball = await packLocalPackage(
      path.join(repositoryRoot, "packages", "generation-renderer"),
      tarballRoot,
      "generation-renderer.tgz"
    );
    const tokensTarball = await packLocalPackage(
      path.join(repositoryRoot, "packages", "design-tokens"),
      tarballRoot,
      "design-tokens.tgz"
    );
    evidence.packages = {
      generation_renderer: { version: "0.1.0", sha256: await sha256File(rendererTarball) },
      design_tokens: { version: "0.1.0", sha256: await sha256File(tokensTarball) }
    };
    const environment = safeEnvironment(runRoot);
    const corpus = JSON.parse(await readFile(corpusPath, "utf8"));
    if (corpus.suite_version !== SECURITY_SUITE_VERSION || corpus.fixture_version !== FIXTURE_VERSION) {
      throw new Error("0098_CORPUS_VERSION_MISMATCH");
    }
    const candidates = [];
    for (const fixtureName of fixtureNames) {
      const candidate = await readSyntheticCandidate(path.join(fixtureRoot, fixtureName));
      candidates.push({
        name: candidate.project_type,
        candidate,
        fixtureId: path.basename(fixtureName, ".json")
      });
      if (candidate.project_type === "landing") {
        candidates.push({
          name: "landing-adversarial",
          candidate: createAdversarialCandidate(candidate, corpus),
          fixtureId: "ast_text_markup_inert"
        });
      }
    }
    for (const candidate of candidates) {
      evidence.candidates.push(await buildAndReview({
        runRoot,
        rendererTarball,
        tokensTarball,
        environment,
        ...candidate
      }));
    }
  } catch (error) {
    evidence.status = "FAIL";
    evidence.gates.static_artifact_security = "FAIL";
    evidence.gates.synthetic_runtime_behavior = "FAIL";
    evidence.findings.push({
      code: error instanceof Error ? error.message.split(":")[0] : "0098_UNKNOWN_FAILURE"
    });
    throw error;
  } finally {
    await rm(runRoot, { recursive: true, force: true });
    await mkdir(path.dirname(evidencePath), { recursive: true });
    await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify(evidence)}\n`);
}

await main();
