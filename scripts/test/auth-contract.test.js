import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import test from "node:test";

const root = process.cwd();

async function pythonFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) return pythonFiles(target);
      return entry.name.endsWith(".py") ? [target] : [];
    })
  );
  return files.flat();
}

test("API pins the approved JWT implementation and crypto extra", async () => {
  const pyproject = await readFile(path.join(root, "apps", "api", "pyproject.toml"), "utf8");

  assert.match(pyproject, /"pyjwt\[crypto\]==2\.13\.0"/);
});

test("JWT library imports remain inside the Supabase infrastructure adapter", async () => {
  const appRoot = path.join(root, "apps", "api", "app");
  const files = await pythonFiles(appRoot);
  const importers = [];

  for (const file of files) {
    const body = await readFile(file, "utf8");
    if (/^(?:from|import)\s+jwt\b/m.test(body)) {
      importers.push(path.relative(root, file).split(path.sep).join("/"));
    }
  }

  assert.deepEqual(importers, ["apps/api/app/infrastructure/auth/supabase_jwt.py"]);
});

test("public API contract keeps Bearer JWT and health exceptions explicit", async () => {
  const openapi = await readFile(
    path.join(root, "packages", "contracts", "openapi.yaml"),
    "utf8"
  );

  assert.match(openapi, /bearerAuth:\s*\n\s+type: http\s*\n\s+scheme: bearer\s*\n\s+bearerFormat: JWT/);
  assert.equal((openapi.match(/security: \[\]/g) ?? []).length, 2);
});
