import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const contractUrl = new URL("../../packages/contracts/job-trace-context.schema.json", import.meta.url);

test("job trace contract carries only the documented versioned identifiers", async () => {
  const contract = JSON.parse(await readFile(contractUrl, "utf8"));

  assert.equal(contract.additionalProperties, false);
  assert.deepEqual(contract.required, [
    "jobId",
    "taskType",
    "payloadVersion",
    "accountId",
    "projectId",
    "correlationId"
  ]);
  assert.equal(contract.properties.jobId.format, "uuid");
  assert.equal(contract.properties.accountId.format, "uuid");
  assert.equal(contract.properties.correlationId.format, "uuid");
  assert.deepEqual(contract.properties.projectId.type, ["string", "null"]);
  assert.equal("payload" in contract.properties, false);
  assert.equal("content" in contract.properties, false);
  assert.equal("authorization" in contract.properties, false);
});

test("HTTP observability middleware is pure ASGI", async () => {
  const middleware = await readFile(
    new URL("../../apps/api/app/api/middleware/observability.py", import.meta.url),
    "utf8"
  );

  assert.doesNotMatch(middleware, /BaseHTTPMiddleware/);
  assert.match(middleware, /async def __call__\(/);
});

test("structured logging contract is versioned and content fields are not allowlisted", async () => {
  const logger = await readFile(
    new URL("../../packages/observability/src/aria_observability/logging.py", import.meta.url),
    "utf8"
  );

  assert.match(logger, /"schema_version": "1"/);
  assert.doesNotMatch(logger, /_OPTIONAL_FIELDS\s*=\s*\{[^}]*"prompt"/s);
  assert.doesNotMatch(logger, /_OPTIONAL_FIELDS\s*=\s*\{[^}]*"response"/s);
  assert.doesNotMatch(logger, /_OPTIONAL_FIELDS\s*=\s*\{[^}]*"authorization"/s);
});
