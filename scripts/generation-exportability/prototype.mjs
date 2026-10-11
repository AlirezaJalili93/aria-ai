import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const PROJECT_TYPES = new Set(["landing", "corporate", "portfolio"]);
const SAFE_PAGE_PATH = /^\/(?:[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*)*)?$/;

export const PROTOTYPE_DEPENDENCIES = Object.freeze({
  "@aria/design-tokens": "file:./vendor/design-tokens.tgz",
  "@aria/generation-renderer": "file:./vendor/generation-renderer.tgz",
  next: "16.4.0",
  react: "19.2.8",
  "react-dom": "19.2.8"
});

function stableUuid(seed) {
  const hex = createHash("sha256").update(seed).digest("hex").slice(0, 32).split("");
  hex[12] = "4";
  hex[16] = ["8", "9", "a", "b"][Number.parseInt(hex[16], 16) % 4];
  return `${hex.slice(0, 8).join("")}-${hex.slice(8, 12).join("")}-${hex.slice(12, 16).join("")}-${hex.slice(16, 20).join("")}-${hex.slice(20).join("")}`;
}

export function canonicalizeSyntheticCandidate(candidate) {
  if (!candidate || !PROJECT_TYPES.has(candidate.project_type) || !Array.isArray(candidate.pages)) {
    throw new Error("0097_INVALID_SYNTHETIC_FIXTURE");
  }
  const paths = new Set();
  for (const page of candidate.pages) {
    if (!SAFE_PAGE_PATH.test(page.path) || paths.has(page.path)) {
      throw new Error("0097_INVALID_PAGE_PATH");
    }
    paths.add(page.path);
  }
  return {
    ...candidate,
    schema_version: "generation_ast_schema_v1",
    pages: candidate.pages.map((page, pageIndex) => ({
      ...page,
      page_id: stableUuid(`${candidate.project_type}:page:${pageIndex}:${page.path}`),
      sections: page.sections.map((section, sectionIndex) => ({
        ...section,
        section_id: stableUuid(
          `${candidate.project_type}:section:${pageIndex}:${sectionIndex}:${section.component_type}`
        ),
        protected_state: "unprotected"
      }))
    }))
  };
}

function routeDirectory(prototypeRoot, pagePath) {
  if (pagePath === "/") return path.join(prototypeRoot, "app");
  return path.join(prototypeRoot, "app", ...pagePath.slice(1).split("/"));
}

function routeModule(pagePath) {
  const depth = pagePath === "/" ? 0 : pagePath.slice(1).split("/").length;
  const dataImport = depth === 0 ? "./prototype-data.js" : `${"../".repeat(depth)}prototype-data.js`;
  return `import { renderCanonicalPage } from "@aria/generation-renderer";
import { assetResolver, canonicalAst } from "${dataImport}";

export default function GeneratedPage() {
  return renderCanonicalPage({ ast: canonicalAst, path: ${JSON.stringify(pagePath)}, assetResolver });
}
`;
}

function prototypeDataModule(ast) {
  const assets = ast.assets.map((assetRef) => ({
    assetRef,
    src: "/generation-fixtures/media.svg",
    width: 1200,
    height: 675
  }));
  return `import { SyntheticAssetResolver } from "@aria/generation-renderer";
import canonicalAst from "../fixtures/canonical-ast.json";

export { canonicalAst };
export const assetResolver = new SyntheticAssetResolver(${JSON.stringify(assets, null, 2)});
`;
}

const ROOT_LAYOUT = `import "@aria/design-tokens/tokens.css";
import "@aria/generation-renderer/styles.css";

export const metadata = {
  title: "Aria Synthetic Exportability Proof",
  robots: { index: false, follow: false }
};

export default function RootLayout({ children }) {
  return (
    <html lang="fa" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
`;

const NEXT_CONFIG = `const nextConfig = {
  output: "export",
  trailingSlash: true
};

export default nextConfig;
`;

const MEDIA_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-labelledby="title description">
  <title id="title">تصویر مصنوعی آریا</title>
  <desc id="description">دارایی محلی و مصنوعی برای آزمون خروجی ایستا</desc>
  <rect width="1200" height="675" fill="#e2e8f0" />
  <path d="M120 520 380 250l210 210 150-150 340 310H120Z" fill="#94a3b8" />
</svg>
`;

export async function writePrototype({ prototypeRoot, candidate, rendererTarball, tokensTarball }) {
  const canonicalAst = canonicalizeSyntheticCandidate(candidate);
  const directories = [
    path.join(prototypeRoot, "app"),
    path.join(prototypeRoot, "fixtures"),
    path.join(prototypeRoot, "public", "generation-fixtures"),
    path.join(prototypeRoot, "vendor")
  ];
  await Promise.all(directories.map((directory) => mkdir(directory, { recursive: true })));

  const packageJson = {
    name: `aria-0097-${canonicalAst.project_type}-static-export-proof`,
    version: "0.0.0",
    private: true,
    type: "module",
    engines: { node: ">=24.0.0", npm: ">=11.0.0" },
    scripts: { build: "next build" },
    dependencies: PROTOTYPE_DEPENDENCIES
  };

  await Promise.all([
    writeFile(path.join(prototypeRoot, "package.json"), `${JSON.stringify(packageJson, null, 2)}\n`, "utf8"),
    writeFile(path.join(prototypeRoot, "next.config.mjs"), NEXT_CONFIG, "utf8"),
    writeFile(path.join(prototypeRoot, "app", "layout.jsx"), ROOT_LAYOUT, "utf8"),
    writeFile(path.join(prototypeRoot, "app", "prototype-data.js"), prototypeDataModule(canonicalAst), "utf8"),
    writeFile(
      path.join(prototypeRoot, "fixtures", "canonical-ast.json"),
      `${JSON.stringify(canonicalAst, null, 2)}\n`,
      "utf8"
    ),
    writeFile(path.join(prototypeRoot, "public", "generation-fixtures", "media.svg"), MEDIA_SVG, "utf8"),
    writeFile(
      path.join(prototypeRoot, "README.md"),
      "# Aria 0097 synthetic static-export proof\n\nDisposable clean-room fixture; no customer data or runtime server.\n",
      "utf8"
    )
  ]);

  if (rendererTarball && tokensTarball) {
    const { copyFile } = await import("node:fs/promises");
    await Promise.all([
      copyFile(rendererTarball, path.join(prototypeRoot, "vendor", "generation-renderer.tgz")),
      copyFile(tokensTarball, path.join(prototypeRoot, "vendor", "design-tokens.tgz"))
    ]);
  }

  for (const page of canonicalAst.pages) {
    const directory = routeDirectory(prototypeRoot, page.path);
    await mkdir(directory, { recursive: true });
    await writeFile(path.join(directory, "page.jsx"), routeModule(page.path), "utf8");
  }

  return canonicalAst;
}

export async function readSyntheticCandidate(fixturePath) {
  return JSON.parse(await readFile(fixturePath, "utf8"));
}

export function outputHtmlPath(outputRoot, pagePath) {
  return pagePath === "/" ? path.join(outputRoot, "index.html") : path.join(outputRoot, pagePath.slice(1), "index.html");
}
