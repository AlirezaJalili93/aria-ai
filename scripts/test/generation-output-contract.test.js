import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const registryPath = "packages/contracts/component-registry-v1.json";
const candidatePath = "packages/contracts/generation-ast-candidate-v1.schema.json";
const canonicalPath = "packages/contracts/generation-ast-v1.schema.json";
const applicationPath = "packages/backend-application/src/aria_backend_application/generation_ast.py";
const adrPath = "docs/adr/ADR-082-generation-component-registry-and-ast.md";

test("0095 registry is immutable, complete and responsive-compatible", async () => {
  const registry = JSON.parse(await readFile(registryPath, "utf8"));
  assert.equal(registry.registry_version, "component_registry_v1");
  assert.deepEqual(registry.project_types, ["landing", "corporate", "portfolio"]);
  assert.equal(Object.keys(registry.components).length, 14);
  assert.deepEqual(registry.breakpoints, [375, 768, 1024, 1440]);
  for (const component of Object.values(registry.components)) {
    assert.ok(component.content_schema_ref);
    assert.ok(Object.keys(component.layout_responsive).length > 0);
  }
  assert.deepEqual(registry.components.Hero.media_required_layouts, ["split_media_start", "split_media_end"]);
  assert.deepEqual(registry.components.AboutSection.media_required_layouts, ["media_start", "media_end"]);
});

test("0095 candidate and canonical schemas separate provider and Application ownership", async () => {
  const candidate = JSON.parse(await readFile(candidatePath, "utf8"));
  const canonical = JSON.parse(await readFile(canonicalPath, "utf8"));
  assert.equal(candidate.$defs.CandidateRoot.properties.schema_version.const, "generation_ast_candidate_v1");
  assert.equal(canonical.properties.schema_version.const, "generation_ast_schema_v1");
  assert.deepEqual(canonical.$defs.ApplicationSection.properties, undefined);
  assert.match(JSON.stringify(canonical), /section_id/);
  assert.match(JSON.stringify(canonical), /protected_state/);
  for (const forbidden of ["remote_url", "action_url", "webhook", "javascript", "className"]) {
    assert.doesNotMatch(JSON.stringify(candidate), new RegExp(`"${forbidden}"`, "i"));
  }
  assert.equal(candidate.$defs.SimpleFormContent.properties.submission_mode.const, "preview_only");
  assert.deepEqual(Object.keys(candidate.$defs.HeroContent.dependentRequired), ["primary_media_asset_ref", "primary_media_alt_text"]);
});

test("0095 Application validates before one atomic finalizer boundary", async () => {
  const source = await readFile(applicationPath, "utf8");
  assert.match(source, /class AssetRegistryPort/);
  assert.match(source, /authorized_for_generation/);
  assert.match(source, /validate_generation_candidate/);
  assert.match(source, /enrich_generation_candidate/);
  assert.match(source, /finalize_validated_output/);
  assert.match(source, /protected_state.*unprotected/s);
  assert.doesNotMatch(source, /requests\.|httpx\.|urllib\.|boto3/);
});

test("0095 ADR preserves deferred boundaries and content-safe observability", async () => {
  const source = await readFile(adrPath, "utf8");
  assert.match(source, /Real Providers, Customer Content and Hosted Generation remain prohibited/);
  assert.match(source, /candidate AST.*prohibited/s);
  assert.match(source, /no migration, endpoint, deployable service or Provider integration/);
  assert.match(source, /Unapproved assumptions:\*\* None/);
});
