import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  PROTOTYPE_DEPENDENCIES,
  canonicalizeSyntheticCandidate,
  readSyntheticCandidate,
  writePrototype
} from "../generation-exportability/prototype.mjs";

const fixtureRoot = path.resolve("evals/generation-output/fixtures/generation_ast_v1");
const fixtureNames = [
  "fa_gen_landing_001.json",
  "fa_gen_corporate_001.json",
  "fa_gen_portfolio_001.json"
];

async function withPrototype(fixtureName, callback) {
  const root = await mkdtemp(path.join(os.tmpdir(), "aria-0097-contract-"));
  try {
    const candidate = await readSyntheticCandidate(path.join(fixtureRoot, fixtureName));
    const ast = await writePrototype({ prototypeRoot: root, candidate });
    await callback({ root, ast });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("0097 pins Next static export and local vendored tarballs", async () => {
  await withPrototype(fixtureNames[0], async ({ root }) => {
    const config = await readFile(path.join(root, "next.config.mjs"), "utf8");
    const packageJson = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
    assert.match(config, /output:\s*"export"/);
    assert.match(config, /trailingSlash:\s*true/);
    assert.deepEqual(packageJson.dependencies, PROTOTYPE_DEPENDENCIES);
    assert.equal(packageJson.dependencies["@aria/generation-renderer"], "file:./vendor/generation-renderer.tgz");
    assert.equal(packageJson.dependencies["@aria/design-tokens"], "file:./vendor/design-tokens.tgz");
    assert.doesNotMatch(JSON.stringify(packageJson), /workspace:|file:\.\.\//);
  });
});

test("0097 writes one fixed Application-owned route wrapper for every AST Page", async () => {
  for (const fixtureName of fixtureNames) {
    await withPrototype(fixtureName, async ({ root, ast }) => {
      for (const page of ast.pages) {
        const segments = page.path === "/" ? [] : page.path.slice(1).split("/");
        const modulePath = path.join(root, "app", ...segments, "page.jsx");
        const source = await readFile(modulePath, "utf8");
        assert.match(source, /renderCanonicalPage/);
        assert.match(source, new RegExp(`path: ${JSON.stringify(page.path).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
        assert.doesNotMatch(source, /fetch\(|eval\(|Function\(|dangerouslySetInnerHTML|use server|generateStaticParams/);
      }
      assert.equal(ast.schema_version, "generation_ast_schema_v1");
      assert.ok(ast.pages.every((page) => page.page_id && page.sections.every((section) => section.section_id)));
    });
  }
});

test("0097 generated source contains no server or remote-runtime surface", async () => {
  await withPrototype(fixtureNames[1], async ({ root }) => {
    const files = [];
    async function visit(directory) {
      for (const entry of await readdir(directory, { withFileTypes: true })) {
        const absolute = path.join(directory, entry.name);
        if (entry.isDirectory()) await visit(absolute);
        else files.push(absolute);
      }
    }
    await visit(root);
    const source = (
      await Promise.all(files.filter((file) => /\.(?:js|jsx|mjs|json|md)$/i.test(file)).map((file) => readFile(file, "utf8")))
    ).join("\n");
    assert.doesNotMatch(source, /https?:\/\//i);
    assert.doesNotMatch(source, /process\.env|fetch\(|XMLHttpRequest|WebSocket|EventSource|server action|route\.js/);
    assert.doesNotMatch(source, /OPENAI_API_KEY|GEMINI_API_KEY|DATABASE_URL|SUPABASE_SERVICE_ROLE/i);
  });
});

test("0097 canonicalization rejects unsafe or duplicate Page paths", async () => {
  const candidate = await readSyntheticCandidate(path.join(fixtureRoot, fixtureNames[0]));
  const unsafe = structuredClone(candidate);
  unsafe.pages[0].path = "https://example.test";
  assert.throws(() => canonicalizeSyntheticCandidate(unsafe), /0097_INVALID_PAGE_PATH/);
  const duplicate = structuredClone(candidate);
  duplicate.pages[1].path = duplicate.pages[0].path;
  assert.throws(() => canonicalizeSyntheticCandidate(duplicate), /0097_INVALID_PAGE_PATH/);
});

test("0097 clean-room runner records non-sensitive evidence and always removes its temp root", async () => {
  const runner = await readFile("scripts/generation-exportability/run-clean-room.mjs", "utf8");
  assert.match(runner, /await rm\(runRoot, \{ recursive: true, force: true \}\)/);
  assert.match(runner, /clean-room-evidence\.json/);
  assert.match(runner, /active_external_references/);
  assert.match(runner, /secret_markers/);
  assert.doesNotMatch(runner, /OPENAI_API_KEY\s*[:=]|GEMINI_API_KEY\s*[:=]/);
});
