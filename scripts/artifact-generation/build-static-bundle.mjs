import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  SyntheticAssetResolver,
  assertCanonicalGenerationAst,
  renderCanonicalPageToStaticMarkup
} from "../../packages/generation-renderer/dist/index.js";

const [inputPath, outputRoot] = process.argv.slice(2);
if (!inputPath || !outputRoot) throw new Error("0100_FIXED_ARGUMENTS_REQUIRED");

const ast = JSON.parse(await readFile(inputPath, "utf8"));
assertCanonicalGenerationAst(ast);
const assets = ast.assets.map((assetRef) => ({
  assetRef,
  src: "/generation-fixtures/media.svg",
  width: 1200,
  height: 675
}));
const resolver = new SyntheticAssetResolver(assets);
const rendererCss = await readFile(
  new URL("../../packages/generation-renderer/styles.css", import.meta.url),
  "utf8"
);
const tokenCss = await readFile(
  new URL("../../packages/design-tokens/tokens.css", import.meta.url),
  "utf8"
);
await mkdir(path.join(outputRoot, "assets"), { recursive: true });
await mkdir(path.join(outputRoot, "generation-fixtures"), { recursive: true });
await writeFile(path.join(outputRoot, "assets", "styles.css"), `${tokenCss}\n${rendererCss}`, "utf8");
await writeFile(
  path.join(outputRoot, "generation-fixtures", "media.svg"),
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" role="img" aria-label="دارایی مصنوعی آریا"><rect width="1200" height="675" fill="#e2e8f0"/></svg>',
  "utf8"
);

for (const page of ast.pages) {
  const relative = page.path === "/" ? "index.html" : `${page.path.slice(1)}/index.html`;
  const target = path.join(outputRoot, ...relative.split("/"));
  await mkdir(path.dirname(target), { recursive: true });
  const markup = renderCanonicalPageToStaticMarkup({ ast, path: page.path, assetResolver: resolver });
  const html = `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><link rel="stylesheet" href="/assets/styles.css"></head><body>${markup}</body></html>`;
  await writeFile(target, html, "utf8");
}
