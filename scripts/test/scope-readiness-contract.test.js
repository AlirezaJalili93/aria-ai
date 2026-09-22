import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("K02 readiness is a pure computed Domain policy", async () => {
  const domain = await read("apps/api/app/modules/scope/domain/readiness.py");
  const scopeModule = await read("apps/api/app/modules/scope/domain/scope_draft.py");
  assert.match(domain, /ready_for_share/);
  assert.match(domain, /status == "open"/);
  assert.match(domain, /severity == "critical"/);
  assert.match(domain, /context_version == context_version/);
  assert.doesNotMatch(domain, /sqlalchemy|fastapi|supabase|ScopeDraftModel|readiness_status/);
  assert.doesNotMatch(scopeModule, /readiness_status|revision/);
});

test("resolved and dismissed Gaps are explicit non-blocking outcomes", async () => {
  const domain = await read("apps/api/app/modules/scope/domain/readiness.py");
  assert.match(domain, /_GAP_STATUSES = frozenset\(\{"open", "resolved", "dismissed"\}\)/);
  assert.match(domain, /gap\.status == "open"/);
  assert.match(domain, /no_open_critical_gaps/);
});

test("K02 does not add persistence, public API, score or content logging", async () => {
  const files = await Promise.all([
    read("apps/api/app/modules/scope/domain/readiness.py"),
    read("apps/api/migrations/env.py"),
    read("packages/contracts/openapi.yaml"),
  ]);
  const [domain, env, openapi] = files;
  assert.doesNotMatch(env, /scope_readiness|readiness_status/);
  assert.doesNotMatch(openapi, /scopeReadiness|readinessScore|ready_for_share/);
  assert.doesNotMatch(domain, /percentage|score|content|title|description|source_refs/);
});
