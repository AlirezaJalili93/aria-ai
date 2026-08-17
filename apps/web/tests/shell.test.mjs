import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const layout = await readFile(new URL("../src/app/layout.tsx", import.meta.url), "utf8");
const page = await readFile(new URL("../src/app/page.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/app/globals.css", import.meta.url), "utf8");
const nextConfig = await readFile(new URL("../next.config.ts", import.meta.url), "utf8");

test("shell is RTL-first and exposes a skip target", () => {
  assert.match(layout, /<html lang="fa" dir="rtl">/);
  assert.match(layout, /href="#main-content"/);
  assert.match(page, /<main id="main-content"/);
});

test("shell imports canonical tokens and reduced-motion handling", () => {
  assert.match(layout, /@aria\/design-tokens\/tokens\.css/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
});

test("shell preserves a single level-one heading", () => {
  assert.equal(page.match(/<h1/g)?.length, 1);
});

test("Next.js does not generate repository instruction files", () => {
  assert.match(nextConfig, /agentRules:\s*false/);
});
