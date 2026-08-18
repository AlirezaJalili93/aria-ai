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
