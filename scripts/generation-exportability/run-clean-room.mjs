import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  copyFile,
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
  outputHtmlPath,
  readSyntheticCandidate,
  writePrototype
} from "./prototype.mjs";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "..", "..");
const evidencePath = path.join(
  repositoryRoot,
  "docs",
  "development",
  "0097-controlled-generation-exportability",
  "clean-room-evidence.json"
);
const fixtures = [
  "fa_gen_landing_001.json",
  "fa_gen_corporate_001.json",
  "fa_gen_portfolio_001.json"
].map((name) => path.join(repositoryRoot, "evals", "generation-output", "fixtures", "generation_ast_v1", name));
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
    "PROCESSOR_ARCHITECTURE"
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
  if (result.error || result.status !== 0) {
    const detail = options.capture ? `\n${result.stdout ?? ""}\n${result.stderr ?? ""}` : "";
    const cause = result.error ? ` (${result.error.message})` : "";
    throw new Error(`0097_COMMAND_FAILED: ${command} ${args.join(" ")}${cause}${detail}`);
  }
  return (result.stdout ?? "").trim();
}

function runNpm(args, options = {}) {
  if (npmCli) return run(process.execPath, [npmCli, ...args], options);
  return run(npmExecutable, args, options);
}

async function sha256(filePath) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(filePath)) hash.update(chunk);
  return hash.digest("hex");
}

async function packLocalPackage(packageDirectory, destination, stableName) {
  const before = new Set(await readdir(destination));
  runNpm(["pack", "--pack-destination", destination, "--silent"], { cwd: packageDirectory });
  const after = await readdir(destination);
  const created = after.filter((name) => !before.has(name) && name.endsWith(".tgz"));
  if (created.length !== 1) throw new Error("0097_TARBALL_CREATION_FAILED");
  const finalPath = path.join(destination, stableName);
  await rename(path.join(destination, created[0]), finalPath);
  return finalPath;
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
  return result;
}

async function scanOutput(outputRoot) {
  const files = await listFiles(outputRoot);
  const textFiles = files.filter((file) => /\.(?:html|css|js|json|txt|svg)$/i.test(file));
  const externalUrlLiterals = new Set();
  const activeExternalReferences = [];
  const secretMarkers = [];
  const secretPattern = /OPENAI_API_KEY|GEMINI_API_KEY|DATABASE_URL|SUPABASE_SERVICE_ROLE|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY/i;
  const urlPattern = /https?:\/\/[^\s"'<>\\)]+/g;
  for (const file of textFiles) {
    const content = await readFile(file, "utf8");
    for (const url of content.match(urlPattern) ?? []) externalUrlLiterals.add(url);
    const activePattern = file.endsWith(".html")
      ? /(?:src|href)=["']https?:\/\/[^"']+/gi
      : file.endsWith(".css")
        ? /url\(\s*["']?https?:\/\//gi
        : null;
    if (activePattern?.test(content)) activeExternalReferences.push(path.relative(outputRoot, file));
    if (secretPattern.test(content)) secretMarkers.push(path.relative(outputRoot, file));
  }
  return {
    active_external_references: activeExternalReferences.sort(),
    external_url_literal_count: externalUrlLiterals.size,
    external_url_literal_sample: [...externalUrlLiterals].sort().slice(0, 20),
    secret_markers: secretMarkers.sort()
  };
}

function contentType(filePath) {
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  return "application/octet-stream";
}

async function withStaticServer(outputRoot, callback) {
  const server = createServer(async (request, response) => {
    try {
      const requestPath = decodeURIComponent(new URL(request.url ?? "/", "http://127.0.0.1").pathname);
      const relative = requestPath.endsWith("/") || path.extname(requestPath) === ""
        ? path.join(requestPath.slice(1), "index.html")
        : requestPath.slice(1);
      const resolved = path.resolve(outputRoot, relative || "index.html");
      if (!resolved.startsWith(`${path.resolve(outputRoot)}${path.sep}`) && resolved !== path.join(outputRoot, "index.html")) {
        response.writeHead(404).end();
        return;
      }
      const metadata = await stat(resolved);
      if (!metadata.isFile()) throw new Error("not a file");
      response.writeHead(200, { "Content-Type": contentType(resolved) });
      createReadStream(resolved).pipe(response);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("0097_STATIC_SERVER_FAILED");
    return await callback(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
  }
}

async function verifyStaticOutput(prototypeRoot, ast) {
  const outputRoot = path.join(prototypeRoot, "out");
  const pages = [];
  for (const page of ast.pages) {
    const htmlPath = outputHtmlPath(outputRoot, page.path);
    const html = await readFile(htmlPath, "utf8");
    if (/<form\b|\baction=|\bmethod=|type=["']submit["']/i.test(html)) {
      throw new Error("0097_SIMPLE_FORM_NETWORK_SURFACE");
    }
    pages.push({ path: page.path, output: path.relative(outputRoot, htmlPath).replaceAll("\\", "/") });
  }
  await withStaticServer(outputRoot, async (origin) => {
    for (const page of ast.pages) {
      const response = await fetch(`${origin}${page.path}`);
      if (!response.ok) throw new Error(`0097_STATIC_NAVIGATION_FAILED: ${page.path}`);
    }
  });
  const scan = await scanOutput(outputRoot);
  if (scan.active_external_references.length || scan.secret_markers.length) {
    throw new Error("0097_OUTPUT_SECURITY_SCAN_FAILED");
  }
  return { pages, scan };
}

function assertPortableLockfile(lockText) {
  const normalizedRepository = repositoryRoot.replaceAll("\\", "/").toLowerCase();
  const normalizedLock = lockText.replaceAll("\\", "/").toLowerCase();
  if (normalizedLock.includes(normalizedRepository) || /workspace:|file:\.\.\//i.test(lockText)) {
    throw new Error("0097_NON_PORTABLE_LOCKFILE");
  }
  if (!lockText.includes("file:vendor/generation-renderer.tgz") || !lockText.includes("file:vendor/design-tokens.tgz")) {
    throw new Error("0097_VENDOR_TARBALLS_NOT_LOCKED");
  }
}

async function main() {
  const runRoot = path.join(os.tmpdir(), `aria-0097-${randomUUID()}`);
  const tarballRoot = path.join(runRoot, "tarballs");
  await mkdir(tarballRoot, { recursive: true });
  const evidence = {
    increment: "0097-controlled-generation-exportability",
    status: "PASS",
    runtime: { node: process.version, npm: "11.6.2", next: "16.4.0" },
    packages: {},
    project_types: [],
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
      generation_renderer: { version: "0.1.0", sha256: await sha256(rendererTarball) },
      design_tokens: { version: "0.1.0", sha256: await sha256(tokensTarball) }
    };

    const environment = safeEnvironment(runRoot);
    for (const fixturePath of fixtures) {
      const candidate = await readSyntheticCandidate(fixturePath);
      const prototypeRoot = path.join(runRoot, candidate.project_type);
      const ast = await writePrototype({ prototypeRoot, candidate, rendererTarball, tokensTarball });
      runNpm(["install", "--package-lock-only", "--ignore-scripts"], {
        cwd: prototypeRoot,
        env: environment
      });
      assertPortableLockfile(await readFile(path.join(prototypeRoot, "package-lock.json"), "utf8"));
      runNpm(["ci", "--ignore-scripts"], { cwd: prototypeRoot, env: environment });
      const audit = JSON.parse(
        runNpm(["audit", "--omit=dev", "--audit-level=high", "--json"], {
          cwd: prototypeRoot,
          env: environment,
          capture: true
        })
      );
      runNpm(["run", "build"], { cwd: prototypeRoot, env: environment });
      const verification = await verifyStaticOutput(prototypeRoot, ast);
      evidence.project_types.push({
        project_type: ast.project_type,
        fixture_id: path.basename(fixturePath, ".json"),
        build: "PASS",
        static_serve: "PASS",
        pages: verification.pages,
        dependency_scan: {
          status: "PASS",
          vulnerabilities: audit.metadata?.vulnerabilities ?? {}
        },
        security_scan: verification.scan
      });
    }
  } catch (error) {
    evidence.status = "FAIL";
    evidence.failure = error instanceof Error ? error.message : "0097_UNKNOWN_FAILURE";
    throw error;
  } finally {
    await rm(runRoot, { recursive: true, force: true });
    await mkdir(path.dirname(evidencePath), { recursive: true });
    await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify(evidence)}\n`);
}

await main();
