import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import test from "node:test";

const root = process.cwd();
const blueprint = await readFile(path.join(root, "render.yaml"), "utf8");

test("Render staging services share the approved Frankfurt region and starter ceiling", () => {
  assert.match(blueprint, /Budget ceiling target: USD 24\/month/);
  assert.equal((blueprint.match(/region: frankfurt/g) ?? []).length, 3);
  assert.equal((blueprint.match(/plan: starter/g) ?? []).length, 3);
  assert.match(blueprint, /type: web\s+name: aria-staging-api/);
  assert.match(blueprint, /type: worker\s+name: aria-staging-worker/);
  assert.match(blueprint, /type: keyvalue\s+name: aria-staging-queue/);
});

test("Render leaves Git branches unpinned so PR previews deploy the verified PR commit", () => {
  assert.doesNotMatch(blueprint, /^\s*branch:/m);
  assert.equal((blueprint.match(/autoDeployTrigger: checksPass/g) ?? []).length, 2);
  assert.equal((blueprint.match(/uv run .*--no-sync/g) ?? []).length, 2);
});

test("Render uses readiness for traffic and persistent no-eviction queue semantics", () => {
  assert.match(blueprint, /healthCheckPath: \/health\/ready/);
  assert.match(blueprint, /maxmemoryPolicy: noeviction/);
  assert.match(blueprint, /persistenceMode: journal-snapshot/);
  assert.match(blueprint, /ipAllowList: \[\]/);
});

test("Render Blueprint keeps runtime-bound values and credentials outside source control", () => {
  for (const key of [
    "DATABASE_URL",
    "STORAGE_ACCESS_KEY",
    "STORAGE_SECRET_KEY",
    "PUBLIC_APP_URL",
    "API_BASE_URL"
  ]) {
    assert.match(
      blueprint,
      new RegExp(`key: ${key}\\n\\s+sync: false`),
      `${key} must be supplied by the Render secret store`
    );
  }
});

test("Worker has no undocumented direct Auth provider dependency", () => {
  const workerSection = blueprint.split("  - type: worker")[1] ?? "";
  assert.doesNotMatch(workerSection, /AUTH_PROVIDER_URL/);
});
