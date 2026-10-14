import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const runnerPath = "scripts/preview-isolation/run-local-proof.mjs";
const browserPath = "scripts/preview-isolation/browser-cdp.mjs";
const adrPath = "docs/adr/ADR-088-preview-isolation-architecture.md";

test("0101 uses separate registrable sites and an exact version-bound Preview origin", async () => {
  const source = await readFile(runnerPath, "utf8");
  assert.match(source, /core\.aria-core\.test/);
  assert.match(source, /aria-preview\.test/);
  assert.match(source, /artifactVersionId/);
  assert.match(source, /VERIFIED_MANIFEST_FILES/);
  assert.match(source, /VERIFIED_MANIFEST_FILES\.has\(manifestPath\)/);
  assert.match(source, /FORBIDDEN_FONT_PATH/);
  assert.match(source, /HOST_NOT_ALLOWED/);
  assert.match(source, /PATH_OUTSIDE_ARTIFACT/);
  assert.doesNotMatch(source, /localhost:\$\{/);
});

test("0101 freezes the opaque-origin sandbox and never adds a messaging bridge", async () => {
  const source = await readFile(runnerPath, "utf8");
  assert.match(source, /sandbox="allow-scripts"/);
  assert.doesNotMatch(source, /allow-same-origin/);
  assert.doesNotMatch(source, /allow-forms|allow-popups|allow-downloads|allow-top-navigation/);
  assert.doesNotMatch(source, /postMessage/);
});

test("0101 derives strict CSP hashes from exact built bytes and sends frame-ancestors by header", async () => {
  const source = await readFile(runnerPath, "utf8");
  assert.match(source, /extractInlineHashes/);
  assert.match(source, /createHash\("sha256"\)/);
  assert.match(source, /frame-ancestors/);
  assert.match(source, /font-src 'none'/);
  assert.match(source, /Content-Security-Policy/);
  assert.match(source, /unsafe-inline.*PROHIBITED/);
  assert.match(source, /unsafe-eval.*PROHIBITED/);
  assert.doesNotMatch(source, /http-equiv=["']Content-Security-Policy/);
});

test("0101 freezes the browser-proven local CORP policy without granting CORS reads", async () => {
  const runner = await readFile(runnerPath, "utf8");
  const adr = await readFile(adrPath, "utf8");
  assert.match(runner, /universal_same_origin/);
  assert.match(runner, /compatibility_cross_origin/);
  assert.match(runner, /runPreviewIsolationBrowserGate/);
  assert.match(adr, /Resolved CORP compatibility decision/);
  assert.match(adr, /Local\/Synthetic policy is frozen/);
  assert.doesNotMatch(runner, /Access-Control-Allow-Origin/i);
  assert.doesNotMatch(runner, /@font-face|rel=["']preload["'][^>]*as=["']font["']/i);
});

test("0101 Browser Gate covers the frozen isolation and negative capabilities", async () => {
  const source = await readFile(browserPath, "utf8");
  for (const marker of [
    "parent_dom_denied",
    "parent_cookie_denied",
    "parent_storage_denied",
    "core_api_denied",
    "form_submission_denied",
    "popup_denied",
    "download_denied",
    "top_navigation_denied",
    "inline_script_denied",
    "image_loaded",
    "system_font_rendered",
    "font_network_requests_zero",
    "style_loaded",
    "script_loaded",
    "unauthorized_embed_denied"
  ]) assert.match(source, new RegExp(marker));
  assert.match(source, /--host-resolver-rules/);
});
