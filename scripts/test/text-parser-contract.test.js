import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const parser = readFileSync(
  resolve(root, "apps/worker/app/application/context_parser.py"),
  "utf8",
);
const adr = readFileSync(resolve(root, "docs/adr/ADR-019-text-parser-contract.md"), "utf8");

test("Text parser stays in the Worker Application boundary", () => {
  assert.match(parser, /class TextParser\(Protocol\)/);
  assert.match(parser, /class CanonicalTextParser/);
  assert.doesNotMatch(parser, /celery|redis|sqlalchemy|asyncpg/i);
});

test("Text parser contract preserves Persian markers and defers hash algorithm", () => {
  for (const term of ["NFC", "ZWNJ", "ZWJ", "CRLF", "canonical_text", "UTF-8"]) {
    assert.match(adr, new RegExp(term));
  }
  assert.match(adr, /hash\s+algorithm itself is not approved/i);
  assert.doesNotMatch(parser, /sha256|hashlib|\bcontent_hash\b/);
  assert.doesNotMatch(parser, /ي\s*→|ك\s*→/);
});
