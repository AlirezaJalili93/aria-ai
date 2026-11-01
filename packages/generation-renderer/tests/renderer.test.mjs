import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  COMPONENT_TYPES,
  GenerationRendererError,
  SyntheticAssetResolver,
  renderCanonicalPageToStaticMarkup
} from "../dist/index.js";

const fixturePaths = [
  "../../evals/generation-output/fixtures/generation_ast_v1/fa_gen_landing_001.json",
  "../../evals/generation-output/fixtures/generation_ast_v1/fa_gen_corporate_001.json",
  "../../evals/generation-output/fixtures/generation_ast_v1/fa_gen_portfolio_001.json"
];

function stableUuid(seed) {
  const hex = createHash("sha256").update(seed).digest("hex").slice(0, 32).split("");
  hex[12] = "4";
  hex[16] = ["8", "9", "a", "b"][Number.parseInt(hex[16], 16) % 4];
  return `${hex.slice(0, 8).join("")}-${hex.slice(8, 12).join("")}-${hex.slice(12, 16).join("")}-${hex.slice(16, 20).join("")}-${hex.slice(20).join("")}`;
}

function canonicalize(candidate) {
  return {
    ...candidate,
    schema_version: "generation_ast_schema_v1",
    pages: candidate.pages.map((page, pageIndex) => ({
      ...page,
      page_id: stableUuid(`${candidate.project_type}:page:${pageIndex}:${page.path}`),
      sections: page.sections.map((section, sectionIndex) => ({
        ...section,
        section_id: stableUuid(`${candidate.project_type}:section:${pageIndex}:${sectionIndex}:${section.component_type}`),
        protected_state: "unprotected"
      }))
    }))
  };
}

function resolverFor(ast) {
  return new SyntheticAssetResolver(ast.assets.map((assetRef) => ({
    assetRef,
    src: "/generation-fixtures/media.svg",
    width: 1200,
    height: 675
  })));
}

async function fixtures() {
  return Promise.all(fixturePaths.map(async (path) => JSON.parse(await readFile(path, "utf8"))));
}

test("0096 rejects Provider candidate output at the renderer boundary", async () => {
  const [candidate] = await fixtures();
  assert.throws(
    () => renderCanonicalPageToStaticMarkup({ ast: candidate, path: "/", assetResolver: resolverFor(candidate) }),
    (error) => error instanceof GenerationRendererError && error.code === "GENERATION_RENDERER_CANONICAL_AST_REQUIRED"
  );
});

test("0096 renders the same canonical page to identical structural markup", async () => {
  const [candidate] = await fixtures();
  const ast = canonicalize(candidate);
  const options = { ast, path: "/", assetResolver: resolverFor(ast) };
  const first = renderCanonicalPageToStaticMarkup(options);
  const second = renderCanonicalPageToStaticMarkup(options);
  assert.equal(first, second);
  assert.equal((first.match(/<main\b/g) ?? []).length, 1);
  assert.equal((first.match(/<h1\b/g) ?? []).length, 1);
  assert.match(first, /aria-gen-visually-hidden[^>]*>صفحه اصلی<\/h1>/);
});

test("0096 three Project Types cover the controlled fourteen-Component map", async () => {
  const candidates = await fixtures();
  const seen = new Set();
  for (const candidate of candidates) {
    const ast = canonicalize(candidate);
    const resolver = resolverFor(ast);
    for (const page of ast.pages) {
      const markup = renderCanonicalPageToStaticMarkup({ ast, path: page.path, assetResolver: resolver });
      assert.equal((markup.match(/<main\b/g) ?? []).length, 1);
      assert.equal((markup.match(/<h1\b/g) ?? []).length, 1);
      assert.doesNotMatch(markup, /<script\b|<iframe\b|dangerouslySetInnerHTML|https?:\/\//i);
    }
    for (const page of ast.pages) for (const section of page.sections) seen.add(section.component_type);
  }
  assert.deepEqual([...seen].sort(), [...COMPONENT_TYPES].sort());
});

test("0096 SimpleForm has no static submission surface", async () => {
  const [candidate] = await fixtures();
  const ast = canonicalize(candidate);
  const markup = renderCanonicalPageToStaticMarkup({ ast, path: "/contact", assetResolver: resolverFor(ast) });
  assert.doesNotMatch(markup, /<form\b|\baction=|\bmethod=|type="submit"|\bname=/i);
  assert.match(markup, /<fieldset\b/);
  assert.match(markup, /<button[^>]*type="button"/);
  assert.match(markup, /<label[^>]*for="aria-gen-field-/);
});

test("0096 unknown or remote Assets fail closed before markup", async () => {
  const [candidate] = await fixtures();
  const ast = canonicalize(candidate);
  assert.throws(
    () => renderCanonicalPageToStaticMarkup({ ast, path: "/", assetResolver: new SyntheticAssetResolver([]) }),
    (error) => error instanceof GenerationRendererError && error.code === "GENERATION_RENDERER_ASSET_NOT_AUTHORIZED"
  );
  assert.throws(
    () => new SyntheticAssetResolver([{ assetRef: ast.assets[0], src: "https://example.test/media.svg", width: 1, height: 1 }]),
    (error) => error instanceof GenerationRendererError && error.code === "GENERATION_RENDERER_ASSET_NOT_AUTHORIZED"
  );
  const unsafeResolver = { resolve: (assetRef) => ({ assetRef, src: "data:image/svg+xml,unsafe", width: 1, height: 1 }) };
  assert.throws(
    () => renderCanonicalPageToStaticMarkup({ ast, path: "/", assetResolver: unsafeResolver }),
    (error) => error instanceof GenerationRendererError && error.code === "GENERATION_RENDERER_ASSET_NOT_AUTHORIZED"
  );
});

test("0096 React escaping keeps AST text inert", async () => {
  const [candidate] = await fixtures();
  const ast = canonicalize(candidate);
  ast.pages[0].title = "<script>alert(1)</script>";
  const markup = renderCanonicalPageToStaticMarkup({ ast, path: "/", assetResolver: resolverFor(ast) });
  assert.doesNotMatch(markup, /<script>/);
  assert.match(markup, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});

test("0096 navigation remains pinned to Page paths in the same AST", async () => {
  const [candidate] = await fixtures();
  const ast = canonicalize(candidate);
  ast.pages[0].sections[0].content.links[0].target_path = "/outside";
  assert.throws(
    () => renderCanonicalPageToStaticMarkup({ ast, path: "/", assetResolver: resolverFor(ast) }),
    (error) => error instanceof GenerationRendererError && error.code === "GENERATION_RENDERER_INVALID_CANONICAL_AST"
  );
});

test("0096 local fixture Asset exists and source contains no execution escape hatch", async () => {
  const source = await readFile("src/renderer.tsx", "utf8");
  const styles = await readFile("styles.css", "utf8");
  const asset = await readFile("fixtures/public/generation-fixtures/media.svg", "utf8");
  assert.match(asset, /^<svg/);
  for (const forbidden of ["dangerouslySetInnerHTML", "iframe", "fetch(", "import(", "eval("]) {
    assert.doesNotMatch(source, new RegExp(forbidden.replace("(", "\\("), "i"));
  }
  assert.doesNotMatch(styles, /\.aria-gen-visually-hidden[^}]*display\s*:\s*none/is);
  assert.doesNotMatch(source, /aria-hidden/);
});
