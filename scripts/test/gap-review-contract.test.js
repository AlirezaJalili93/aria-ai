import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("J04 current-version list binds deterministic cursors to filters", async () => {
  const router = await read("apps/api/app/api/routers/clarifications.py");
  const repository = await read("apps/api/app/modules/gaps/infrastructure/clarification_repository.py");
  assert.match(repository, /ProjectModel\.current_context_version/);
  assert.match(repository, /if current_version == 0:[\s\S]*return \(\)/);
  assert.match(repository, /GapModel\.context_version == current_version/);
  assert.match(repository, /GapModel\.created_at\.desc\(\), GapModel\.id\.desc\(\)/);
  for (const filter of ["status", "severity", "gap_type"]) assert.match(router, new RegExp(`"${filter}"`));
  assert.match(router, /payload\.get\("filters"\) != filters/);
});

test("J04 preserves chronological historical Clarification reads", async () => {
  const repository = await read("apps/api/app/modules/gaps/infrastructure/clarification_repository.py");
  const router = await read("apps/api/app/api/routers/clarifications.py");
  assert.match(repository, /ClarificationModel\.created_at\.asc\(\), ClarificationModel\.id\.asc\(\)/);
  assert.doesNotMatch(repository, /list_clarification_history[\s\S]{0,1600}current_context_version/);
  assert.match(router, /HistoryResolutionResponse/);
  assert.doesNotMatch(router.match(/class HistoryResolutionResponse[\s\S]*?class ClarificationHistoryResponse/)?.[0] ?? "", /actor_id|author_id|account_id/);
});

test("accepted assumption requires both canonical eligibility fields", async () => {
  const service = await read("apps/api/app/modules/gaps/application/clarification_service.py");
  assert.match(service, /gap\.gap_type == "unsupported_assumption"[\s\S]*and gap\.suggested_resolution_type == "validate_assumption"/);
});

test("dismiss is a separate bodyless idempotent human command", async () => {
  const router = await read("apps/api/app/api/routers/clarifications.py");
  const service = await read("apps/api/app/modules/gaps/application/clarification_service.py");
  assert.match(router, /@router\.post\("\/\{gap_id\}\/dismiss"/);
  assert.match(router, /Header\(alias="Idempotency-Key"\)/);
  assert.doesNotMatch(router, /class DismissGapRequest/);
  assert.match(service, /GAP_DISMISS_ROUTE_KEY/);
  assert.match(service, /response_status=204/);
  assert.match(service, /status="dismissed"/);
  assert.match(service, /resolved_at=None/);
});

test("J04 contract does not add deferred automation or mutable severity", async () => {
  const combined = `${await read("apps/api/app/api/routers/clarifications.py")}\n${await read("apps/web/src/features/gaps/gap-review.tsx")}`;
  assert.doesNotMatch(combined, /recompute|readiness.?score|confidence.?score|generateQuestion|updateSeverity/i);
});
