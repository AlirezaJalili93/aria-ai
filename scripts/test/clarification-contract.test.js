import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("J03-A separates question and resolution commands", async () => {
  const router = await read("apps/api/app/api/routers/clarifications.py");
  const openapi = await read("packages/contracts/openapi.yaml");

  for (const source of [router, openapi]) {
    assert.match(source, /\{gap_id\}\/clarifications/);
    assert.match(source, /\{clarification_id\}\/resolutions/);
    assert.match(source, /Idempotency-Key|IdempotencyKeyHeader/);
  }
  assert.match(router, /expected_updated_at/);
  assert.match(router, /\{gap_id\}\/dismiss/);
  assert.match(router, /DismissGapCommand\(idempotency_key=idempotency_key\)/);
});

test("Clarification and resolution vocabularies are closed and human-terminal", async () => {
  const domain = await read("apps/api/app/modules/gaps/domain/clarification.py");
  const migration = await read("apps/api/migrations/versions/0016_clarifications.py");

  for (const value of ["open", "answered", "ignored"]) {
    assert.match(domain, new RegExp(`"${value}"`));
    assert.match(migration, new RegExp(`'${value}'`));
  }
  for (const value of [
    "provided_information",
    "internal_decision",
    "accepted_assumption",
    "ignored",
  ]) {
    assert.match(domain, new RegExp(`"${value}"`));
    assert.match(migration, new RegExp(`'${value}'`));
  }
  assert.match(domain, /ClarificationAuthorType = Literal\["user", "client"\]/);
  assert.doesNotMatch(domain, /ClarificationAuthorType = Literal\[[^\]]*system/);
});

test("database contract preserves tenant history and exact-open deduplication", async () => {
  const migration = await read("apps/api/migrations/versions/0016_clarifications.py");

  assert.match(migration, /ux_clarifications_open_question/);
  assert.match(migration, /status = 'open'/);
  assert.match(migration, /uq_clarification_resolutions_clarification/);
  assert.match(migration, /ondelete="RESTRICT"/g);
  assert.match(migration, /ENABLE ROW LEVEL SECURITY/g);
  assert.match(migration, /clarification_resolution_answer/);
});

test("resolution state machine evaluates the Gap independently", async () => {
  const service = await read(
    "apps/api/app/modules/gaps/application/clarification_service.py",
  );

  assert.match(service, /has_open_questions/);
  assert.match(service, /status="resolved"/);
  assert.match(service, /async def dismiss_gap/);
  assert.doesNotMatch(service, /status="dismissed"[\s\S]{0,400}resolution_type == "ignored"/);
});

test("AI-04 boundary is provider neutral and real adapters remain absent", async () => {
  const port = await read(
    "apps/api/app/modules/gaps/application/clarification_question_generation.py",
  );

  assert.match(port, /class ClarificationQuestionGenerator\(Protocol\)/);
  assert.match(port, /ClarificationQuestionCandidate/);
  assert.doesNotMatch(port, /openai|anthropic|gemini|redis|celery/i);
});

test("safe observability admits metadata but not question or answer payloads", async () => {
  const service = await read(
    "apps/api/app/modules/gaps/application/clarification_service.py",
  );
  const logger = await read("packages/observability/src/aria_observability/logging.py");
  const emissions = service.match(/self\._event_logger\.emit\([\s\S]{0,700}?\n\s*\)/g) ?? [];

  assert.match(logger, /"clarification_id"/);
  assert.match(logger, /"resolution_type"/);
  assert.doesNotMatch(emissions.join("\n"), /question_text=|answer_text=|source_refs=/);
});
