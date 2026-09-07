import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("logical M006 implements only the approved Gap schema", async () => {
  const migration = await read("apps/api/migrations/versions/0014_gaps.py");

  assert.match(migration, /revision:\s*str\s*=\s*["']0014_gaps["']/);
  assert.match(migration, /down_revision:\s*str\s*\|\s*None\s*=\s*["']0013_requirement_crud["']/);
  assert.match(migration, /context_version >= 1/);
  for (const gapType of [
    "missing_information",
    "ambiguity",
    "conflict",
    "decision_required",
    "unsupported_assumption",
    "scope_risk",
  ]) {
    assert.match(migration, new RegExp(`['"]${gapType}['"]`));
  }
  for (const severity of ["critical", "high", "medium", "low"]) {
    assert.match(migration, new RegExp(`['"]${severity}['"]`));
  }
  for (const status of ["open", "resolved", "dismissed"]) {
    assert.match(migration, new RegExp(`['"]${status}['"]`));
  }
  assert.match(migration, /resolved_at IS NULL OR status = 'resolved'/);
  assert.match(migration, /jsonb_typeof\(source_refs\) = 'array'/);
  assert.match(migration, /ondelete=["']RESTRICT["']/g);
  assert.match(migration, /ALTER TABLE gaps ENABLE ROW LEVEL SECURITY/);
  assert.doesNotMatch(migration, /missing_info['"]|context_version_id|question|clarification|accepted_assumption|affected_requirement_ids|suggested_resolution_type|title|explanation|created_by/i);
});

test("Gap module preserves layering and the J01-only boundary", async () => {
  const domain = await read("apps/api/app/modules/gaps/domain/gap.py");
  const application = await read("apps/api/app/modules/gaps/application/gap_service.py");
  const repository = await read("apps/api/app/modules/gaps/infrastructure/repository.py");

  assert.doesNotMatch(domain, /fastapi|sqlalchemy|supabase|aria_observability/i);
  assert.doesNotMatch(application, /fastapi|sqlalchemy|supabase/i);
  assert.match(application, /resolve_provenance/);
  assert.match(application, /["']gap\.created["']/);
  assert.doesNotMatch(application, /gap\.resolved|gap\.dismissed|generate|detect|clarification/i);
  assert.match(repository, /ContextSourceVersionModel\.parse_status == ["']ready["']/);
  assert.match(repository, /ContextSourceVersionModel\.account_id == account_id/);
  assert.match(repository, /ContextSourceVersionModel\.project_id == project_id/);
});

test("J01 updates the canonical data mirror without exposing a public API", async () => {
  const model = await read("docs/architecture/data-model.md");
  const openapi = await read("packages/contracts/openapi.yaml");
  const adr = await read("docs/adr/ADR-035-gap-domain-contract.md");

  assert.match(model, /missing_information\/ambiguity\/conflict\/decision_required\/unsupported_assumption\/scope_risk/);
  assert.match(model, /`resolved_at` فقط در status resolved/);
  assert.doesNotMatch(openapi, /\/gaps/);
  assert.match(adr, /Status:\*\* Accepted/);
  assert.match(adr, /No `title`, `explanation`, `created_by`/);
});

test("Gap creation logging excludes provenance and customer content", async () => {
  const application = await read("apps/api/app/modules/gaps/application/gap_service.py");
  const emitStart = application.indexOf('"gap.created"');
  const emitCall = application.slice(emitStart, application.indexOf("return persisted", emitStart));

  assert.match(emitCall, /gap_id/);
  assert.match(emitCall, /context_version/);
  assert.match(emitCall, /gap_type/);
  assert.match(emitCall, /severity/);
  assert.doesNotMatch(emitCall, /persisted\.source_refs|canonical_text|raw_text/);
});
