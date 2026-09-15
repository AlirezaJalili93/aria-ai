import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const schemaUrl = new URL("../../packages/contracts/product-analytics.schema.json", import.meta.url);
const backendUrl = new URL("../../packages/observability/src/aria_observability/product_analytics.py", import.meta.url);
const loggerUrl = new URL("../../packages/observability/src/aria_observability/logging.py", import.meta.url);
const webUrl = new URL("../../apps/web/src/features/analytics/product-events.ts", import.meta.url);

const serverEvents = [
  "project_created",
  "context_added",
  "structuring_started",
  "structuring_completed",
  "requirements_generated",
  "gap_detected",
  "gap_resolved",
  "scope_generated",
  "scope_version_saved"
];
const interactionEvents = [
  "project_opened",
  "project_type_selected",
  "requirement_edited",
  "requirement_removed",
  "scope_edited"
];

test("product analytics schema freezes the versioned envelope and safe property vocabulary", async () => {
  const schema = JSON.parse(await readFile(schemaUrl, "utf8"));
  assert.equal(schema.additionalProperties, false);
  assert.deepEqual(schema.required, [
    "event_id", "event_name", "event_category", "schema_version", "occurred_at",
    "account_id", "project_id", "actor_id", "properties"
  ]);
  assert.equal(schema.properties.event_category.const, "product_analytics");
  assert.equal(schema.properties.schema_version.const, "1");
  assert.deepEqual(schema.properties.event_name.enum, [...serverEvents, ...interactionEvents]);
  assert.deepEqual(schema.properties.project_id.type, ["string", "null"]);
  assert.equal(schema.properties.properties.additionalProperties, false);
  assert.deepEqual(Object.keys(schema.properties.properties.properties).sort(), [
    "context_version", "gap_id", "project_type", "requirement_id", "role", "section_id",
    "source_id", "source_surface", "version_no"
  ].sort());
});

test("server contract keeps per-event allowlists, stable IDs and no provider dependency", async () => {
  const backend = await readFile(backendUrl, "utf8");
  const logger = await readFile(loggerUrl, "utf8");
  for (const eventName of serverEvents) assert.match(backend, new RegExp(`"${eventName}"`));
  assert.match(backend, /_EVENT_PROPERTIES/);
  assert.match(backend, /uuid5/);
  assert.match(logger, /_product_event_ids/);
  assert.doesNotMatch(backend, /openai|anthropic|google\.genai|posthog|amplitude/i);
  for (const forbidden of ["prompt", "raw_text", "canonical_text", "title", "description", "email", "jwt"])
    assert.doesNotMatch(backend, new RegExp(`['\"]${forbidden}['\"]`, "i"));
});

test("web analytics exposes only separate interaction events and preserves pre-project null context", async () => {
  const web = await readFile(webUrl, "utf8");
  for (const eventName of interactionEvents) assert.match(web, new RegExp(`"${eventName}"`));
  for (const eventName of serverEvents) assert.doesNotMatch(web, new RegExp(`"${eventName}"`));
  assert.match(web, /event_category: "product_analytics"/);
  assert.match(web, /project_id: event\.projectId \?\? null/);
  assert.match(web, /crypto\.randomUUID\(\)/);
  assert.doesNotMatch(web, /title|description|raw_text|canonical_text|prompt|jwt|email/i);
});
