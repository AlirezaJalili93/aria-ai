import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(path, "utf8");

test("membership resolution preserves the Identity module layering", async () => {
  const useCase = await read(
    "apps/api/app/modules/identity/application/membership_resolution.py"
  );
  const repository = await read(
    "apps/api/app/modules/identity/infrastructure/membership_resolution.py"
  );

  assert.match(useCase, /MembershipResolutionRepository/);
  assert.doesNotMatch(useCase, /fastapi|sqlalchemy|supabase/i);
  assert.match(repository, /AccountMembershipModel\.user_id == user_id/);
  assert.match(repository, /AccountMembershipModel\.account_id == account_id/);
});

test("S1-B03 does not invent the future Tenant transport contract", async () => {
  const useCase = await read(
    "apps/api/app/modules/identity/application/membership_resolution.py"
  );

  assert.doesNotMatch(useCase, /Header|Cookie|Session|Request|Depends/);
});

test("membership status and role are resolved server-side", async () => {
  const useCase = await read(
    "apps/api/app/modules/identity/application/membership_resolution.py"
  );
  const repository = await read(
    "apps/api/app/modules/identity/infrastructure/membership_resolution.py"
  );

  assert.match(useCase, /membership\.status != ACTIVE_MEMBERSHIP_STATUS/);
  assert.match(repository, /role=cast\(MembershipRole, row\.role\)/);
  assert.match(repository, /status=cast\(MembershipStatus, row\.status\)/);
});

test("membership lookup uses the existing M001 subject-account uniqueness", async () => {
  const migration = await read(
    "apps/api/migrations/versions/0001_identity_projection.py"
  );
  const repository = await read(
    "apps/api/app/modules/identity/infrastructure/membership_resolution.py"
  );

  assert.match(migration, /UniqueConstraint\(\s*"account_id", "user_id"/);
  assert.match(repository, /AccountMembershipModel\.user_id == user_id/);
  assert.match(repository, /AccountMembershipModel\.account_id == account_id/);
});

test("architecture validation excludes generated local evidence and caches", async () => {
  const validator = await read("scripts/validate-architecture.mjs");
  const gitignore = await read(".gitignore");

  assert.match(gitignore, /^\.data\/$/m);
  assert.match(validator, /skippedDirectories = new Set\(\[[\s\S]*"\.data"/);
});
