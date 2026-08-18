import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import test from "node:test";

const root = process.cwd();
const railwayRoot = path.join(root, "infra", "railway");

const apiConfig = JSON.parse(
  await readFile(path.join(railwayRoot, "api.railway.json"), "utf8")
);
const workerConfig = JSON.parse(
  await readFile(path.join(railwayRoot, "worker.railway.json"), "utf8")
);
const apiDockerfile = await readFile(path.join(railwayRoot, "api.Dockerfile"), "utf8");
const workerDockerfile = await readFile(path.join(railwayRoot, "worker.Dockerfile"), "utf8");

test("Railway keeps API and Worker as separate deployables in the same EU staging region", () => {
  const expectedRegion = {
    "europe-west4-drams3a": { numReplicas: 1 }
  };

  assert.deepEqual(apiConfig.deploy.multiRegionConfig, expectedRegion);
  assert.deepEqual(workerConfig.deploy.multiRegionConfig, expectedRegion);
  assert.equal(apiConfig.build.dockerfilePath, "infra/railway/api.Dockerfile");
  assert.equal(workerConfig.build.dockerfilePath, "infra/railway/worker.Dockerfile");
});

test("Railway deploys locked Python 3.12 API and Worker images without runtime dependency sync", () => {
  for (const [dockerfile, project] of [
    [apiDockerfile, "api"],
    [workerDockerfile, "worker"]
  ]) {
    assert.match(dockerfile, /^FROM python:3\.12\.13-slim-bookworm$/m);
    assert.match(dockerfile, /uv==0\.12\.5/);
    assert.match(dockerfile, new RegExp(`uv sync --project apps/${project} --locked --no-dev`));
    assert.match(
      dockerfile,
      new RegExp(`uv[\\s\\S]+run[\\s\\S]+--project[\\s\\S]+apps/${project}[\\s\\S]+--no-sync`)
    );
    assert.match(dockerfile, /^USER aria$/m);
  }
});

test("Railway uses readiness for API admission and a bounded free-plan restart policy", () => {
  assert.equal(apiConfig.deploy.healthcheckPath, "/health/ready");
  assert.equal(apiConfig.deploy.healthcheckTimeout, 300);
  assert.equal(apiConfig.deploy.restartPolicyType, "ON_FAILURE");
  assert.equal(apiConfig.deploy.restartPolicyMaxRetries, 10);
  assert.equal(workerConfig.deploy.restartPolicyType, "ON_FAILURE");
  assert.equal(workerConfig.deploy.restartPolicyMaxRetries, 10);
  assert.equal("healthcheckPath" in workerConfig.deploy, false);
});

test("Railway configuration is branch-neutral and contains no runtime credentials", () => {
  const source = JSON.stringify({ apiConfig, workerConfig, apiDockerfile, workerDockerfile });

  assert.doesNotMatch(source, /agent\/staging-runtime|\"branch\"/i);
  assert.doesNotMatch(source, /DATABASE_URL|QUEUE_BROKER_URL|STORAGE_ACCESS_KEY|STORAGE_SECRET_KEY/);
  assert.doesNotMatch(source, /postgres(?:ql)?:\/\/[^\s]+:[^\s]+@/i);
  assert.doesNotMatch(source, /redis(?:s)?:\/\/[^\s]+:[^\s]+@/i);
});

test("The superseded Render Blueprint is absent", async () => {
  await assert.rejects(access(path.join(root, "render.yaml")));
});

test("Worker keeps no undocumented direct Auth provider dependency", () => {
  assert.doesNotMatch(workerDockerfile, /AUTH_PROVIDER_URL|AUTH_JWKS_URL|AUTH_AUDIENCE/);
});
