import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const reviewPath = "docs/development/0102-local-preview-publication-and-capability/migration-review.sql";
const sql = await readFile(reviewPath, "utf8");
const executable = sql.replace(/--[^\n]*/g, "");
const migration = await readFile("apps/api/migrations/versions/0040_preview_publication.py", "utf8");
const helpers = [...executable.matchAll(
  /CREATE FUNCTION aria_internal\.(\w+)\(([\s\S]*?)\)\s+RETURNS ([\s\S]*?)AS \$body\$([\s\S]*?)\$body\$;/g
)];

test("0102 fifth failure helper migration exactly embeds approved review SQL without widening authority", async () => {
  const review = await readFile("docs/development/0102-local-preview-publication-and-capability/failure-helper-review.sql", "utf8");
  const active = await readFile("apps/api/migrations/versions/0041_preview_failure.py", "utf8");
  const normalize = (value) => value.replace(/--[^\n]*/g, "").replace(/\s+/g, " ").trim();
  const statements = [...active.matchAll(/r"""([\s\S]*?)"""/g)].map((item) => item[1]);
  assert.equal(normalize(statements.join("\n")), normalize(review));
  assert.match(active, /down_revision: str \| None = "0040_preview_publication"/);
  assert.doesNotMatch(active, /read_text|read_bytes|ALTER TABLE|ALTER ROLE|DROP ROLE|CASCADE|DROP OWNED/);
  assert.match(active, /SELECT \(error_code\) ON public\.jobs TO aria_preview_runtime_owner/);
  assert.match(active, /SECURITY DEFINER SET search_path = ''/);
  assert.match(active, /pg_catalog\.pg_locks/);
  assert.match(active, /l\.pid = pg_catalog\.pg_backend_pid\(\)/);
  assert.match(active, /DROP FUNCTION aria_internal\.fail_preview\(UUID, UUID, TEXT\)/);
  assert.match(active, /REVOKE SELECT \(error_code\) ON public\.jobs FROM aria_preview_runtime_owner/);
});

test("0102 preserves the historical SQL review snapshot independently of activation evidence", () => {
  assert.match(sql, /NOT APPLIED and NOT in the active Alembic chain/);
  assert.match(sql, /exact SQL review pending/);
  const tables = [...executable.matchAll(/CREATE TABLE ([\w.]+)/g)].map((item) => item[1]);
  assert.deepEqual(tables, [
    "public.preview_representations", "public.preview_publications",
    "aria_internal.preview_execution_claims"
  ]);
});

test("0102 active migration matches the reviewed executable SQL without a docs runtime dependency", () => {
  const statements = [...migration.matchAll(/r"""([\s\S]*?)"""/g)].map((item) => item[1]);
  const normalize = (value) => value.replace(/--[^\n]*/g, "").replace(/\s+/g, " ").trim();
  assert.equal(normalize(statements.join("\n")), normalize(executable));
  assert.match(migration, /down_revision: str \| None = "0039_artifact_generation_runtime"/);
  assert.doesNotMatch(migration, /read_text|read_bytes|Path\(|open\(/);
});

test("0102 approved downgrade checks all three tables under lock before removing fixed objects", () => {
  const down = migration.slice(migration.indexOf("def downgrade()"));
  assert.match(down, /ACCESS EXCLUSIVE MODE/);
  for (const table of ["public.preview_publications", "public.preview_representations",
    "aria_internal.preview_execution_claims"]) {
    assert.ok(down.includes(`SELECT 1 FROM ${table}`));
  }
  assert.ok(down.indexOf("ACCESS EXCLUSIVE MODE") < down.indexOf("SELECT EXISTS"));
  assert.ok(down.indexOf("Preview downgrade denied: state exists") < down.indexOf("DROP FUNCTION"));
  assert.match(down, /pg_catalog\.pg_shdepend/);
  assert.match(down, /if not outside_dependency/);
  assert.doesNotMatch(down, /op\.execute\([^)]*(?:CASCADE|DROP OWNED)/);
  assert.doesNotMatch(down, /FROM aria_worker/);
});

test("0102 reuses only a preserved safe Role without widening its locked attributes", () => {
  const up = migration.slice(migration.indexOf("def upgrade()"), migration.indexOf("def downgrade()"));
  assert.match(up, /rolcanlogin, rolinherit, rolsuper, rolbypassrls, rolcreatedb/);
  assert.match(up, /rolcreaterole, rolreplication/);
  assert.match(up, /if any\(attributes\)/);
  assert.match(up, /Preview runtime owner attributes rejected/);
  assert.doesNotMatch(up, /ALTER ROLE/);
});

test("0102 limits definers to four fixed signatures and excludes executable SQL fragments", () => {
  assert.deepEqual(helpers.map((item) => [item[1], item[2].replace(/\s+/g, " ").trim()]), [
    ["claim_preview", "p_job UUID, p_event UUID"],
    ["finalize_preview", "p_job UUID, p_event UUID, p_ref TEXT, p_hash TEXT"],
    ["release_preview", "p_job UUID, p_event UUID"],
    ["resolve_preview", "p_hash TEXT"]
  ]);
  for (const [, , , header, body] of helpers) {
    assert.match(header, /SECURITY DEFINER SET search_path = ''/);
    assert.match(body, /END;\s*$/);
    assert.doesNotMatch(body, /\bEXECUTE\b|\bset_config\b|\bSET\s+ROLE\b|\bSET\s+LOCAL\b/i);
    assert.doesNotMatch(body, /\b(?:FROM|JOIN)\s+(?!public\.|aria_internal\.)[a-z_]+/i);
  }
});

test("0102 helper owner has no table ownership, role membership or direct Worker table grants", () => {
  assert.match(executable, /NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION/);
  assert.doesNotMatch(executable, /ALTER TABLE[^;]*OWNER TO aria_preview_runtime_owner/i);
  assert.doesNotMatch(executable, /GRANT aria_preview_runtime_owner TO/i);
  assert.doesNotMatch(executable, /GRANT\s+(?!EXECUTE\b)[^;]*\bTO aria_worker\b/i);
  assert.match(executable, /REVOKE ALL ON public\.preview_representations, public\.preview_publications,\s*aria_internal\.preview_execution_claims FROM PUBLIC, aria_worker/);
  assert.equal((executable.match(/ENABLE ROW LEVEL SECURITY/g) ?? []).length, 3);
  assert.match(executable, /GRANT SELECT \([^)]*started_at, attempt_count\)\s*ON public\.jobs/);
  for (const [signature] of [
    ["claim_preview\\(UUID, UUID\\)"], ["finalize_preview\\(UUID, UUID, TEXT, TEXT\\)"],
    ["release_preview\\(UUID, UUID\\)"], ["resolve_preview\\(TEXT\\)"]
  ]) {
    assert.match(executable, new RegExp(`REVOKE ALL ON FUNCTION aria_internal\\.${signature} FROM PUBLIC`));
    assert.match(executable, new RegExp(`GRANT EXECUTE ON FUNCTION aria_internal\\.${signature} TO aria_worker`));
  }
  assert.match(executable, /FROM anon;/);
  assert.match(executable, /FROM authenticated;/);
});

test("0102 claim/finalize lock targets before validating the complete bound graph and mutating", () => {
  for (const name of ["claim_preview", "finalize_preview"]) {
    const body = helpers.find((item) => item[1] === name)[4];
    assert.ok(body.indexOf("FOR UPDATE OF r") < body.indexOf("INTO b"));
    assert.ok(body.indexOf("IF NOT FOUND") < body.indexOf("UPDATE public."));
    for (const table of ["jobs", "preview_publications", "preview_representations", "artifact_versions",
      "artifacts", "projects", "accounts", "outbox_events"]) {
      assert.match(body, new RegExp(`public\\.${table}\\b`));
    }
    assert.match(body, /a\.artifact_hash = r\.source_hash/);
    assert.match(body, /j\.payload_ref = pg_catalog\.jsonb_build_object/);
    assert.match(body, /e\.delivery_channel = 'job_queue'/);
    assert.match(body, /p\.revoked_at IS NULL/);
    assert.match(body, /IF p_job IS NULL OR p_event IS NULL/);
  }
});

test("0102 finalization and release require exact same-backend Job/Event ownership", () => {
  const finalize = helpers.find((item) => item[1] === "finalize_preview")[4];
  const release = helpers.find((item) => item[1] === "release_preview")[4];
  assert.match(finalize, /c\.owner_backend_pid = pg_catalog\.pg_backend_pid\(\)/);
  assert.match(finalize, /e\.id = p_event/);
  assert.match(finalize, /IF p_ref <> 'preview\/'/);
  assert.match(finalize, /UPDATE public\.jobs SET status = 'succeeded'/);
  assert.match(release, /c\.job_id = p_job AND c\.outbox_event_id = p_event/);
  assert.match(release, /c\.owner_backend_pid = pg_catalog\.pg_backend_pid\(\)/);
  assert.match(release, /IF FOUND THEN\s*PERFORM pg_catalog\.pg_advisory_unlock/);
});

test("0102 capability resolution uses hash only with synchronous expiry and shared revocation lock", () => {
  const body = helpers.find((item) => item[1] === "resolve_preview")[4];
  assert.match(body, /p_hash IS NULL OR p_hash !~/);
  assert.match(body, /p\.token_hash = p_hash/);
  assert.match(body, /p\.expires_at > pg_catalog\.clock_timestamp\(\)/);
  assert.match(body, /p\.revoked_at IS NULL/);
  assert.match(body, /FOR SHARE;/);
  assert.ok(body.indexOf("FOR SHARE;") < body.indexOf("pg_catalog.clock_timestamp()"));
  assert.doesNotMatch(body, /raw_token|public_token|token_available/);
  assert.doesNotMatch(executable, /ON DELETE CASCADE/);
});
