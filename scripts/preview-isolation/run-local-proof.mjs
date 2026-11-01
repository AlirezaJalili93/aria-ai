import { createHash, randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { mkdir, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { runPreviewIsolationBrowserGate } from "./browser-cdp.mjs";

const ARTIFACT_VERSION = "artifact-v1";
const artifactVersionId = ARTIFACT_VERSION;
const CORE_HOST = "core.aria-core.test";
const PREVIEW_HOST = "v-artifact-v1.aria-preview.test";
const ATTACKER_HOST = "attacker.aria-other.test";
const HOST_NOT_ALLOWED = "HOST_NOT_ALLOWED";
const PATH_OUTSIDE_ARTIFACT = "PATH_OUTSIDE_ARTIFACT";
const VERIFIED_MANIFEST_FILES = Object.freeze(new Set([
  "index.html",
  "contact-proof",
  "assets/style.css",
  "assets/runtime.js",
  "assets/proof.svg"
]));
const FORBIDDEN_FONT_PATH = /\.(?:woff2?|ttf|otf)$/i;
// unsafe-inline and unsafe-eval are PROHIBITED; hashes are derived from exact bytes below.

function sha256Base64(value) {
  return createHash("sha256").update(Buffer.from(value, "utf8")).digest("base64");
}

function extractInlineHashes(html) {
  const hashes = { script: [], style: [] };
  for (const [kind, pattern] of [
    ["script", /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi],
    ["style", /<style[^>]*>([\s\S]*?)<\/style>/gi]
  ]) {
    for (const match of html.matchAll(pattern)) hashes[kind].push(`'sha256-${sha256Base64(match[1])}'`);
  }
  return hashes;
}

function cspHeader({ coreOrigin, html }) {
  const hashes = extractInlineHashes(html);
  return [
    "default-src 'none'",
    "base-uri 'none'",
    `script-src 'self' ${hashes.script.join(" ")}`,
    `style-src 'self' ${hashes.style.join(" ")}`,
    "img-src 'self'",
    "font-src 'none'",
    "connect-src 'none'",
    "form-action 'none'",
    "object-src 'none'",
    "frame-src 'none'",
    "worker-src 'none'",
    `frame-ancestors ${coreOrigin}`
  ].join("; ");
}

function htmlForPreview({ coreOrigin, previewOrigin, pathName }) {
  const simpleForm = pathName.endsWith("/contact-proof")
    ? '<section aria-labelledby="contact-title"><h2 id="contact-title">فرم پیش‌نمایش</h2><label for="contact-name">نام</label><input id="contact-name" required><button type="button">ثبت محلی</button></section>'
    : "";
  const html = `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>Aria synthetic preview</title><link rel="stylesheet" href="/artifacts/${ARTIFACT_VERSION}/assets/style.css"><script>document.documentElement.dataset.inlineHash = "verified";</script></head><body><main class="aria-gen-page"><h1>پیش‌نمایش مصنوعی</h1><p>Artifact ${ARTIFACT_VERSION}</p><img src="/artifacts/${ARTIFACT_VERSION}/assets/proof.svg" alt="تصویر آزمون">${simpleForm}<script src="/artifacts/${ARTIFACT_VERSION}/assets/runtime.js"></script></main></body></html>`;
  return { html, csp: cspHeader({ coreOrigin, html }), pathName, previewOrigin };
}

function headers({ corp, csp, contentType }) {
  return {
    "Cache-Control": "no-store",
    "Content-Security-Policy": csp,
    "Cross-Origin-Resource-Policy": corp,
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "X-Content-Type-Options": "nosniff",
    "Content-Type": contentType
  };
}

async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("0101_SERVER_ADDRESS_FAILED");
  return address.port;
}

async function startSites({ corp }) {
  const counters = { form: 0, download: 0, api: 0, font_requests: 0, core_requests: 0, preview_requests: 0 };
  let coreOrigin;
  let previewOrigin;
  let attackerOrigin;
  let corePort;
  let previewPort;
  let attackerPort;
  const previewPage = () => htmlForPreview({ coreOrigin, previewOrigin, pathName: "/" });

  const core = createServer((request, response) => {
    counters.core_requests += 1;
    if (request.headers.host !== `${CORE_HOST}:${corePort}`) { response.writeHead(421).end(HOST_NOT_ALLOWED); return; }
    const url = new URL(request.url ?? "/", `http://${CORE_HOST}`);
    if (request.method === "POST" && url.pathname === "/api/form") { counters.form += 1; response.writeHead(200).end(); return; }
    if (url.pathname === "/api/sentinel") { counters.api += 1; response.writeHead(200).end("blocked-control"); return; }
    if (url.pathname === "/download-sentinel") { counters.download += 1; response.writeHead(200).end("synthetic"); return; }
    if (url.pathname !== "/" && url.pathname !== "/contact-proof" && url.pathname !== "/escaped" && url.pathname !== "/popup") { response.writeHead(404).end(); return; }
    const previewPath = url.pathname === "/contact-proof" ? "contact-proof" : "index.html";
    const iframe = `${previewOrigin}/artifacts/${ARTIFACT_VERSION}/${previewPath}`;
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>Core synthetic harness</title></head><body><p>Core sentinel</p><iframe id="preview" sandbox="allow-scripts" src="${iframe}"></iframe></body></html>`;
    response.writeHead(200, {
      ...headers({ corp: "same-origin", csp: `default-src 'none'; base-uri 'none'; frame-src ${previewOrigin}; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; form-action 'none'; object-src 'none'; frame-ancestors 'none'`, contentType: "text/html; charset=utf-8" }),
      "Set-Cookie": "aria_core_sentinel=synthetic; SameSite=Lax"
    }).end(html);
  });

  const preview = createServer((request, response) => {
    counters.preview_requests += 1;
    if (request.headers.host !== `${PREVIEW_HOST}:${previewPort}`) { response.writeHead(421).end(HOST_NOT_ALLOWED); return; }
    if (/[\\]|\.\.|%2e/i.test(request.url ?? "")) { response.writeHead(404).end(PATH_OUTSIDE_ARTIFACT); return; }
    const url = new URL(request.url ?? "/", `http://${PREVIEW_HOST}`);
    if (FORBIDDEN_FONT_PATH.test(url.pathname)) { counters.font_requests += 1; response.writeHead(404).end(PATH_OUTSIDE_ARTIFACT); return; }
    const prefix = `/artifacts/${artifactVersionId}`;
    const manifestPath = url.pathname.startsWith(`${prefix}/`) ? url.pathname.slice(prefix.length + 1) : "";
    if (!VERIFIED_MANIFEST_FILES.has(manifestPath)) { response.writeHead(404).end(PATH_OUTSIDE_ARTIFACT); return; }
    const common = { corp, csp: "", contentType: "application/octet-stream" };
    if (url.pathname === `${prefix}/index.html` || url.pathname === `${prefix}/contact-proof`) {
      const { html, csp } = htmlForPreview({ coreOrigin, previewOrigin, pathName: url.pathname });
      // Document delivery is tested separately from subresource CORP. The universal candidate
      // remains applied to every script/style/font/image response below.
      response.writeHead(200, headers({ ...common, corp: "cross-origin", csp, contentType: "text/html; charset=utf-8" })).end(html); return;
    }
    if (url.pathname === `${prefix}/assets/style.css`) {
      response.writeHead(200, headers({ ...common, csp: "default-src 'none'; style-src 'self'; font-src 'none'", contentType: "text/css; charset=utf-8" })).end(".aria-gen-page{direction:rtl;font-family:system-ui,sans-serif}"); return;
    }
    if (url.pathname === `${prefix}/assets/runtime.js`) {
      response.writeHead(200, headers({ ...common, csp: "default-src 'none'; script-src 'self'", contentType: "text/javascript; charset=utf-8" })).end("globalThis.__ARIA_0101_RUNTIME__ = true;"); return;
    }
    if (url.pathname === `${prefix}/assets/proof.svg`) {
      response.writeHead(200, headers({ ...common, csp: "default-src 'none'", contentType: "image/svg+xml" })).end("<svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'><rect width='8' height='8' fill='#2b6cb0'/></svg>"); return;
    }
    response.writeHead(404).end(PATH_OUTSIDE_ARTIFACT);
  });

  const attacker = createServer((request, response) => {
    if (request.headers.host !== `${ATTACKER_HOST}:${attackerPort}`) { response.writeHead(421).end(HOST_NOT_ALLOWED); return; }
    const iframe = `${previewOrigin}/artifacts/${ARTIFACT_VERSION}/index.html`;
    response.writeHead(200, headers({ corp: "same-origin", csp: "default-src 'none'; frame-src *; style-src 'self'; script-src 'self'; frame-ancestors 'none'", contentType: "text/html; charset=utf-8" })).end(`<!doctype html><html><body><iframe src="${iframe}"></iframe></body></html>`);
  });

  [corePort, previewPort, attackerPort] = await Promise.all([listen(core), listen(preview), listen(attacker)]);
  coreOrigin = `http://${CORE_HOST}:${corePort}`;
  previewOrigin = `http://${PREVIEW_HOST}:${previewPort}`;
  attackerOrigin = `http://${ATTACKER_HOST}:${attackerPort}`;
  return { core, preview, attacker, counters, coreOrigin, previewOrigin, attackerOrigin };
}

async function closeSites(sites) {
  await Promise.all([sites.core, sites.preview, sites.attacker].map((server) => new Promise((resolve) => server.close(() => resolve()))));
}

function passesBrowserGate(result) {
  if (!result || result.error_code) return false;
  const requiredResources = ["image_loaded", "system_font_rendered", "font_network_requests_zero", "style_loaded", "script_loaded", "inline_hash_script_loaded"];
  const requiredIsolation = [
    "parent_dom_denied",
    "parent_cookie_denied",
    "parent_storage_denied",
    "own_storage_denied",
    "core_api_denied",
    "inline_script_denied",
    "popup_denied",
    "form_submission_denied",
    "download_denied",
    "top_navigation_denied",
    "simple_form_local_validation",
    "unauthorized_embed_denied"
  ];
  return requiredResources.every((name) => result.resources?.[name] === true)
    && requiredIsolation.every((name) => result.isolation?.[name] === true)
    && result.oopif === true;
}

async function runMatrix() {
  const root = path.join(os.tmpdir(), `aria-0101-${randomUUID()}`);
  await mkdir(root, { recursive: true });
  // Keep the profile path unique and disposable; no product state is written.
  const evidence = { increment: "0101-preview-isolation-architecture", status: "PENDING", corp_matrix: {}, browser_gate: null, cleanup: "pending" };
  for (const [name, corp] of [["universal_same_origin", "same-origin"], ["compatibility_cross_origin", "cross-origin"]]) {
    const sites = await startSites({ corp });
    try {
      try {
        evidence.corp_matrix[name] = await runPreviewIsolationBrowserGate({
          coreOrigin: sites.coreOrigin,
          previewOrigin: sites.previewOrigin,
          attackerOrigin: sites.attackerOrigin,
          profileRoot: path.join(root, name),
          serverCounters: sites.counters
        });
      } catch (error) {
        evidence.corp_matrix[name] = { status: "INCOMPATIBLE_OR_UNAVAILABLE", error_code: error instanceof Error ? error.message : "0101_BROWSER_GATE_FAILED" };
      }
    } finally { await closeSites(sites); }
  }
  const compatible = evidence.corp_matrix.compatibility_cross_origin;
  const universal = evidence.corp_matrix.universal_same_origin;
  evidence.browser_gate = passesBrowserGate(compatible) ? "PASS" : "PENDING_BROWSER_GATE";
  evidence.corp_matrix.universal_same_origin_compatible = passesBrowserGate(universal);
  evidence.corp_matrix.compatibility_candidate_compatible = passesBrowserGate(compatible);
  evidence.status = evidence.corp_matrix.compatibility_candidate_compatible ? "PASS" : "PENDING_BROWSER_GATE";
  await rm(root, { recursive: true, force: true });
  evidence.cleanup = "completed";
  return evidence;
}

const evidence = await runMatrix();
process.stdout.write(`${JSON.stringify(evidence)}\n`);
